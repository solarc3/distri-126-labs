"""Módulo Pub/Sub para la diseminación de mensajes con enrutamiento inteligente."""

import logging
import time
from collections.abc import Callable, Sequence
from typing import Any, Literal, TypeAlias, TypedDict, cast

from civicmesh.membership.view import MembershipView
from civicmesh.protocol import JsonValue, PeerId, ProtocolError, Sobre
from civicmesh.transport import EndpointError, Transport, parse_endpoint

logger = logging.getLogger(__name__)

CanalPubSub: TypeAlias = Literal["objetivo", "subjetivo"]
CallbackMensaje: TypeAlias = Callable[[dict[str, Any]], None]

# Mapa estático de adyacencia geográfica de comunas para la región metropolitana
COMUNAS_ADYACENTES: dict[str, set[str]] = {
    "santiago": {
        "providencia",
        "recoleta",
        "independencia",
        "quinta_normal",
        "estacion_central",
        "san_miguel",
        "pedro_aguirre_cerda",
        "nunoa",
    },
    "providencia": {"santiago", "las_condes", "vitacura", "nunoa", "recoleta"},
    "las_condes": {"providencia", "vitacura", "lo_barnechea", "la_reina"},
    "vitacura": {"providencia", "las_condes", "lo_barnechea", "huechuraba"},
    "nunoa": {"santiago", "providencia", "la_reina", "macul", "san_joaquin"},
    "recoleta": {
        "santiago",
        "providencia",
        "huechuraba",
        "conchali",
        "independencia",
    },
    "independencia": {"santiago", "recoleta", "conchali", "quinta_normal"},
    "quinta_normal": {
        "santiago",
        "pudahuel",
        "renca",
        "estacion_central",
        "independencia",
    },
    "estacion_central": {
        "santiago",
        "quinta_normal",
        "pudahuel",
        "maipu",
        "cerrillos",
        "pedro_aguirre_cerda",
    },
    "san_miguel": {
        "santiago",
        "pedro_aguirre_cerda",
        "san_joaquin",
        "la_cisterna",
        "ramon_freire",
    },
    "macul": {"nunoa", "la_reina", "penalolen", "san_joaquin", "la_florida"},
    "la_reina": {"las_condes", "providencia", "nunoa", "macul", "penalolen"},
}


def normalizar_tópico(tópico: str) -> str:
    """Normaliza un tópico/comuna a minúsculas y sin espacios adicionales."""
    return tópico.strip().lower()


def obtener_comunas_interes(tópico: str) -> set[str]:
    """Devuelve el tópico normalizado y sus comunas geográficamente adyacentes."""
    norm = normalizar_tópico(tópico)
    adyacentes = COMUNAS_ADYACENTES.get(norm, set())
    return {norm} | set(adyacentes)


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


class SubscriptionManager:
    """Gestiona las suscripciones de los peers a comunas o regiones."""

    def __init__(self) -> None:
        # Mapea peer_id -> set de tópicos normalizados a los que está suscrito
        self._suscripciones_peers: dict[str, set[str]] = {}
        # Suscripciones del nodo local
        self._suscripciones_locales: set[str] = set()

    def suscribir_local(self, tópico: str) -> None:
        self._suscripciones_locales.add(normalizar_tópico(tópico))

    def desuscribir_local(self, tópico: str) -> None:
        self._suscripciones_locales.discard(normalizar_tópico(tópico))

    def es_suscrito_local(self, tópico: str) -> bool:
        norm = normalizar_tópico(tópico)
        comunas_interes = obtener_comunas_interes(norm)
        return bool(self._suscripciones_locales & comunas_interes)

    def registrar_suscripcion_peer(self, peer_id: str, tópicos: Sequence[str]) -> None:
        self._suscripciones_peers[peer_id] = {normalizar_tópico(t) for t in tópicos}

    def remover_peer(self, peer_id: str) -> None:
        self._suscripciones_peers.pop(peer_id, None)

    def esta_interesado_peer(self, peer_id: str, tópico: str) -> bool:
        """Indica si un peer está interesado en un tópico o en comunas vecinas."""
        suscripciones = self._suscripciones_peers.get(peer_id)
        if suscripciones is None:
            # Si no hay registro explícito, por defecto asumimos interés potencial
            return True

        interes = obtener_comunas_interes(tópico)
        return bool(suscripciones & interes)

    def hay_interesados(self, peers_vivos: Sequence[str], tópico: str) -> bool:
        """Determina si al menos un peer vivo de la lista está interesado."""
        if not peers_vivos:
            return False

        return any(self.esta_interesado_peer(pid, tópico) for pid in peers_vivos)


def should_forward(
    msg: dict[str, Any],
    topic: str,
    local_view: MembershipView | Sequence[str] | dict[str, Any],
    subscriptions: SubscriptionManager | None = None,
) -> bool:
    """Evalúa si un mensaje Pub/Sub debe ser reenviado según su TTL e interés.

    Evita el flooding ciego verificando:
    1. Que el mensaje no haya expirado (TTL > 0).
    2. Que la prioridad sea válida (>= 1).
    3. Que existan peers activos en la vista local verdaderamente interesados.
    """
    ttl = msg.get("ttl")
    if ttl is None or isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0:
        return False

    priority = msg.get("priority", 1)
    if isinstance(priority, bool) or not isinstance(priority, int) or priority < 1:
        return False

    # Extraer peers vivos de la vista local
    if isinstance(local_view, MembershipView):
        peers_vivos = local_view.vivos()
    elif isinstance(local_view, dict):
        # Si es un dict de estados o digest
        peers_vivos = [
            pid
            for pid, info in local_view.items()
            if (isinstance(info, dict) and info.get("estado") == "alive")
            or not isinstance(info, dict)
        ]
    else:
        peers_vivos = list(local_view)

    if not peers_vivos:
        return False

    # Si hay gestor de suscripciones, comprobar que algún peer vivo esté interesado
    if subscriptions is not None:
        return subscriptions.hay_interesados(peers_vivos, topic)

    return True


class PubSub:
    """Componente Pub/Sub para publicación, suscripción y enrutamiento."""

    def __init__(
        self,
        vista: MembershipView,
        transport: Transport,
        subscriptions: SubscriptionManager | None = None,
        fanout: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if vista.yo != transport.peer_id:
            raise ValueError("la vista y el transporte representan peers distintos")
        if fanout is not None and fanout <= 0:
            raise ValueError("el fanout de pubsub debe ser positivo")

        self._vista = vista
        self._transport = transport
        self._subscriptions = subscriptions or SubscriptionManager()
        self._fanout = fanout
        self._clock = clock

        self._vistos: set[str] = set()
        self._callbacks: list[CallbackMensaje] = []
        self._secuencia_local = 0
        self._mensajes_recibidos: list[PubSubPayload] = []

    @property
    def subscriptions(self) -> SubscriptionManager:
        return self._subscriptions

    def suscribir(self, topic: str) -> None:
        self._subscriptions.suscribir_local(topic)

    def subscribe(self, topic: str) -> None:
        self._subscriptions.suscribir_local(topic)

    def unsubscribe(self, topic: str) -> None:
        self._subscriptions.desuscribir_local(topic)

    def agregar_callback(self, callback: CallbackMensaje) -> None:
        self._callbacks.append(callback)

    def publish(
        self,
        topic: str,
        content: JsonValue,
        channel: CanalPubSub = "objetivo",
        priority: int = 1,
        ttl: int = 5,
    ) -> str:
        """Publica un nuevo mensaje Pub/Sub desde el nodo local."""
        self._secuencia_local += 1
        ts = int(self._clock())
        msg_id = f"{self._transport.peer_id}:{ts}:{self._secuencia_local}"

        payload: PubSubPayload = {
            "id": msg_id,
            "topic": topic,
            "channel": channel,
            "content": content,
            "ttl": ttl,
            "priority": priority,
            "origin": self._transport.peer_id,
        }

        self._vistos.add(msg_id)

        # Si el propio nodo está suscrito, se procesa localmente
        if self._subscriptions.es_suscrito_local(topic):
            self._procesar_entrega_local(payload)

        # Reenviar a peers activos si corresponde según should_forward
        self._difundir(payload, remitente_original=self._transport.peer_id)
        return msg_id

    def handle(self, sobre: Sobre) -> None:
        if sobre["tipo"] != "pubsub":
            raise ProtocolError("PubSub solo procesa sobres de tipo pubsub")

        payload = validar_payload_pubsub(sobre)
        msg_id = payload["id"]

        if msg_id in self._vistos:
            logger.debug("mensaje pubsub duplicado omitido: %s", msg_id)
            return

        self._vistos.add(msg_id)

        # Entrega local si hay interés
        if self._subscriptions.es_suscrito_local(payload["topic"]):
            self._procesar_entrega_local(payload)

        # Reenviar si no ha expirado y debe reenviarse
        self._difundir(payload, remitente_original=sobre["from"])

    def tick(self, _now: float) -> None:
        """Tick del componente PubSub."""
        # Mantener el tamaño del conjunto de vistos acotado
        if len(self._vistos) > 10000:
            # Retener los últimos elementos
            self._vistos = set(list(self._vistos)[-5000:])

    def _procesar_entrega_local(self, payload: PubSubPayload) -> None:
        self._mensajes_recibidos.append(payload)
        for cb in self._callbacks:
            try:
                cb(cast(dict[str, Any], payload))
            except Exception:
                logger.exception("error en callback local de PubSub")

    def _difundir(
        self,
        payload: PubSubPayload,
        remitente_original: str,
    ) -> None:
        ttl = payload["ttl"]
        if ttl <= 1:
            return  # Al decrementar a 0 expiraría

        payload_forward = dict(payload)
        payload_forward["ttl"] = ttl - 1

        if not should_forward(
            payload_forward,
            payload["topic"],
            self._vista,
            self._subscriptions,
        ):
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
            pid
            for pid in self._vista.vivos()
            if pid != remitente_original and pid != payload["origin"]
        ]

        if self._fanout is not None and len(destinatarios) > self._fanout:
            destinatarios = destinatarios[: self._fanout]

        for objetivo in destinatarios:
            try:
                self._transport.send(objetivo, sobre)
            except (EndpointError, OSError) as error:
                logger.warning(
                    "no se pudo enviar pubsub a %s: %s",
                    objetivo,
                    error,
                )
