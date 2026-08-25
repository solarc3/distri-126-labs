"""Módulo Pub/Sub para la diseminación de mensajes con enrutamiento inteligente."""

import heapq
import logging
import random
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, Literal, TypeAlias, TypedDict, cast

from civicmesh.comunas import normalizar_tópico, obtener_comunas_interes
from civicmesh.membership.view import MembershipView, RandomSource
from civicmesh.protocol import JsonValue, PeerId, ProtocolError, Sobre
from civicmesh.transport import EndpointError, Transport, parse_endpoint

logger = logging.getLogger(__name__)

CanalPubSub: TypeAlias = Literal["objetivo", "subjetivo"]
CallbackMensaje: TypeAlias = Callable[[dict[str, Any]], None]
EnvioPendiente: TypeAlias = tuple[int, int, PeerId, Sobre]

MAX_MENSAJES_VISTOS = 10_000
MENSAJES_VISTOS_RETENIDOS = 5_000


class PoliticaCanal(TypedDict):
    ttl: int
    priority: int


class PoliticasCanales(TypedDict):
    objetivo: PoliticaCanal
    subjetivo: PoliticaCanal


class PubSubPayload(TypedDict):
    id: str
    topic: str
    channel: CanalPubSub
    content: JsonValue
    ttl: int
    priority: int
    origin: PeerId


def validar_payload_pubsub(sobre: Sobre) -> PubSubPayload:
    """Valida la estructura y tipos del payload de un mensaje Pub/Sub."""
    payload = sobre["payload"]
    campos_requeridos = {
        "id",
        "topic",
        "channel",
        "content",
        "ttl",
        "priority",
        "origin",
    }
    if not campos_requeridos.issubset(payload):
        raise ProtocolError("faltan campos obligatorios en el payload de pubsub")

    msg_id = payload["id"]
    if not isinstance(msg_id, str) or not msg_id:
        raise ProtocolError("id debe ser un texto no vacio")

    topic = payload["topic"]
    if not isinstance(topic, str) or not topic:
        raise ProtocolError("topic debe ser un texto no vacio")

    channel = payload["channel"]
    if channel not in ("objetivo", "subjetivo"):
        raise ProtocolError("channel debe ser 'objetivo' o 'subjetivo'")

    ttl = payload["ttl"]
    if isinstance(ttl, bool) or not isinstance(ttl, int):
        raise ProtocolError("ttl debe ser un entero")

    priority = payload["priority"]
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ProtocolError("priority debe ser un entero")

    origin = payload["origin"]
    if not isinstance(origin, str) or not origin:
        raise ProtocolError("origin debe ser un peer ID no vacio")

    try:
        parse_endpoint(origin)
    except EndpointError as error:
        raise ProtocolError(f"origin peer ID invalido: {origin}") from error

    return cast(PubSubPayload, payload)


def _peer_interesado(
    local_view: MembershipView,
    peer_id: PeerId,
    topic: str,
) -> bool:
    comunas_interes = obtener_comunas_interes(topic)
    suscripciones = {
        normalizar_tópico(suscripcion)
        for suscripcion in local_view.topics_de(peer_id)
    }
    return bool(suscripciones & comunas_interes)


def should_forward(
    msg: dict[str, Any],
    topic: str,
    local_view: MembershipView,
) -> bool:
    """Indica si queda TTL y existe algún peer vivo interesado."""
    ttl = msg.get("ttl")
    if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0:
        return False

    priority = msg.get("priority")
    if isinstance(priority, bool) or not isinstance(priority, int) or priority < 1:
        return False

    return any(
        _peer_interesado(local_view, peer_id, topic)
        for peer_id in local_view.vivos()
    )


def _validar_politica(canal: CanalPubSub, politica: PoliticaCanal) -> None:
    ttl = politica["ttl"]
    priority = politica["priority"]
    if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0:
        raise ValueError(f"el TTL de {canal} debe ser un entero positivo")
    if (
        isinstance(priority, bool)
        or not isinstance(priority, int)
        or priority <= 0
    ):
        raise ValueError(f"la prioridad de {canal} debe ser un entero positivo")


def _copiar_politicas(politicas: PoliticasCanales) -> PoliticasCanales:
    copia: PoliticasCanales = {
        "objetivo": {
            "ttl": politicas["objetivo"]["ttl"],
            "priority": politicas["objetivo"]["priority"],
        },
        "subjetivo": {
            "ttl": politicas["subjetivo"]["ttl"],
            "priority": politicas["subjetivo"]["priority"],
        },
    }
    _validar_politica("objetivo", copia["objetivo"])
    _validar_politica("subjetivo", copia["subjetivo"])

    if copia["objetivo"]["ttl"] == copia["subjetivo"]["ttl"]:
        raise ValueError("los canales deben tener TTL distintos")
    if copia["objetivo"]["priority"] == copia["subjetivo"]["priority"]:
        raise ValueError("los canales deben tener prioridades distintas")
    return copia


class PubSub:
    """Componente Pub/Sub para publicación, suscripción y enrutamiento."""

    def __init__(
        self,
        vista: MembershipView,
        transport: Transport,
        politicas: PoliticasCanales,
        fanout: int | None = None,
        rng: RandomSource | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if vista.yo != transport.peer_id:
            raise ValueError("la vista y el transporte representan peers distintos")
        if fanout is not None and fanout <= 0:
            raise ValueError("el fanout de pubsub debe ser positivo")

        self._vista = vista
        self._transport = transport
        self._politicas = _copiar_politicas(politicas)
        self._fanout = fanout
        self._rng = rng or random.Random()
        self._clock = clock

        self._vistos: OrderedDict[str, None] = OrderedDict()
        self._pendientes: list[EnvioPendiente] = []
        self._secuencia_envio = 0
        self._callbacks: list[CallbackMensaje] = []
        self._secuencia_local = 0
        self._mensajes_recibidos: list[PubSubPayload] = []

    def subscribe(self, topic: str) -> None:
        normalizado = normalizar_tópico(topic)
        topics = self._vista.topics_de(self._vista.yo)
        if all(
            normalizar_tópico(suscripcion) != normalizado
            for suscripcion in topics
        ):
            topics.append(normalizado)
            self._vista.set_topics(topics)

    def unsubscribe(self, topic: str) -> None:
        normalizado = normalizar_tópico(topic)
        topics = [
            suscripcion
            for suscripcion in self._vista.topics_de(self._vista.yo)
            if normalizar_tópico(suscripcion) != normalizado
        ]
        self._vista.set_topics(topics)

    def agregar_callback(self, callback: CallbackMensaje) -> None:
        self._callbacks.append(callback)

    def publish(
        self,
        topic: str,
        content: JsonValue,
        channel: CanalPubSub = "objetivo",
    ) -> str:
        """Publica usando el TTL y la prioridad configurados para el canal."""
        politica = self._politicas[channel]
        self._secuencia_local += 1
        ts = int(self._clock())
        msg_id = f"{self._transport.peer_id}:{ts}:{self._secuencia_local}"

        payload: PubSubPayload = {
            "id": msg_id,
            "topic": topic,
            "channel": channel,
            "content": content,
            "ttl": politica["ttl"],
            "priority": politica["priority"],
            "origin": self._transport.peer_id,
        }

        self._recordar(msg_id)

        if _peer_interesado(self._vista, self._vista.yo, topic):
            self._procesar_entrega_local(payload)

        self._difundir(payload, remitente_original=self._transport.peer_id)
        return msg_id

    def handle(self, sobre: Sobre) -> None:
        if sobre["tipo"] != "pubsub":
            raise ProtocolError("PubSub solo procesa sobres de tipo pubsub")

        payload = validar_payload_pubsub(sobre)
        if not self._recordar(payload["id"]):
            logger.debug("mensaje pubsub duplicado omitido: %s", payload["id"])
            return

        if _peer_interesado(self._vista, self._vista.yo, payload["topic"]):
            self._procesar_entrega_local(payload)

        self._difundir(payload, remitente_original=sobre["from"])

    def tick(self, _now: float) -> None:
        """Poda IDs antiguos y despacha reenvíos por prioridad."""
        if len(self._vistos) > MAX_MENSAJES_VISTOS:
            while len(self._vistos) > MENSAJES_VISTOS_RETENIDOS:
                self._vistos.popitem(last=False)

        while self._pendientes:
            _prioridad, _secuencia, objetivo, sobre = heapq.heappop(
                self._pendientes
            )
            try:
                self._transport.send(objetivo, sobre)
            except (EndpointError, OSError) as error:
                logger.warning(
                    "no se pudo enviar pubsub a %s: %s",
                    objetivo,
                    error,
                )

    def _recordar(self, msg_id: str) -> bool:
        if msg_id in self._vistos:
            return False
        self._vistos[msg_id] = None
        return True

    def _procesar_entrega_local(self, payload: PubSubPayload) -> None:
        self._mensajes_recibidos.append(payload)
        for callback in self._callbacks:
            try:
                callback(cast(dict[str, Any], payload))
            except Exception:
                logger.exception("error en callback local de PubSub")

    def _difundir(
        self,
        payload: PubSubPayload,
        remitente_original: str,
    ) -> None:
        ttl = payload["ttl"]
        if ttl <= 1:
            return

        payload_forward = dict(payload)
        payload_forward["ttl"] = ttl - 1
        if not should_forward(payload_forward, payload["topic"], self._vista):
            return

        sobre = cast(
            Sobre,
            {
                "tipo": "pubsub",
                "from": self._transport.peer_id,
                "payload": payload_forward,
            },
        )
        destinatarios = [
            peer_id
            for peer_id in self._vista.vivos()
            if peer_id != remitente_original
            and peer_id != payload["origin"]
            and _peer_interesado(self._vista, peer_id, payload["topic"])
        ]

        if self._fanout is not None and len(destinatarios) > self._fanout:
            destinatarios = self._rng.sample(destinatarios, self._fanout)

        for objetivo in destinatarios:
            self._secuencia_envio += 1
            heapq.heappush(
                self._pendientes,
                (
                    -payload["priority"],
                    self._secuencia_envio,
                    objetivo,
                    sobre,
                ),
            )
