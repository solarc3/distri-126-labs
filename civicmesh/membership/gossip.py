import logging
import time
from collections.abc import Callable
from typing import TypeAlias, TypedDict, cast

from civicmesh.membership.view import DigestState, MembershipView, RandomSource
from civicmesh.protocol import ProtocolError, Sobre
from civicmesh.transport import EndpointError, Transport, parse_endpoint

logger = logging.getLogger(__name__)

Clock: TypeAlias = Callable[[], float]


class GossipPayload(TypedDict):
    heartbeat: int
    topics: list[str]
    peers: dict[str, DigestState]


def _validar_topics(valor: object, ruta: str) -> None:
    if not isinstance(valor, list) or not all(
        isinstance(topic, str) for topic in valor
    ):
        raise ProtocolError(f"{ruta} debe ser una lista de textos")


def _validar_payload_gossip(sobre: Sobre) -> GossipPayload:
    payload = sobre["payload"]
    campos_requeridos = {"heartbeat", "topics", "peers"}
    if not campos_requeridos.issubset(payload):
        raise ProtocolError("faltan campos obligatorios en el payload de gossip")

    heartbeat = payload["heartbeat"]
    if isinstance(heartbeat, bool) or not isinstance(heartbeat, int) or heartbeat < 0:
        raise ProtocolError("heartbeat debe ser un entero no negativo")

    _validar_topics(payload["topics"], "topics")

    peers = payload["peers"]
    if not isinstance(peers, dict):
        raise ProtocolError("peers debe ser un objeto JSON")

    for peer_id, estado_peer in peers.items():
        if not isinstance(peer_id, str):
            raise ProtocolError("los peer ID del digest deben ser textos")
        try:
            parse_endpoint(peer_id)
        except EndpointError as error:
            raise ProtocolError(f"peer ID invalido en digest: {peer_id}") from error

        if not isinstance(estado_peer, dict):
            raise ProtocolError(f"estado invalido para peer {peer_id}")
        if not {"heartbeat", "topics"}.issubset(estado_peer):
            raise ProtocolError(f"faltan campos para peer {peer_id}")

        peer_heartbeat = estado_peer["heartbeat"]
        if isinstance(peer_heartbeat, bool) or not isinstance(peer_heartbeat, int):
            raise ProtocolError(f"heartbeat invalido para peer {peer_id}")
        if peer_heartbeat < 0:
            raise ProtocolError(f"heartbeat invalido para peer {peer_id}")
        _validar_topics(estado_peer["topics"], f"topics de peer {peer_id}")

    return cast(GossipPayload, payload)


class Gossip:
    def __init__(
        self,
        vista: MembershipView,
        transport: Transport,
        rng: RandomSource,
        *,
        fanout: int = 1,
        interval: float = 1.0,
        clock: Clock = time.monotonic,
    ) -> None:
        if fanout < 0:
            raise ValueError("el fanout no puede ser negativo")
        if interval <= 0:
            raise ValueError("el intervalo debe ser positivo")
        if vista.yo != transport.peer_id:
            raise ValueError("la vista y el transporte representan peers distintos")

        self._vista = vista
        self._transport = transport
        self._rng = rng
        self._fanout = fanout
        self._interval = interval
        self._clock = clock

        self._heartbeat = 0
        self._next_send = 0.0

    def handle(self, sobre: Sobre) -> None:
        if sobre["tipo"] != "gossip":
            raise ProtocolError("Gossip solo procesa sobres de tipo gossip")

        payload = _validar_payload_gossip(sobre)
        self._vista.contacto_directo(
            sobre["from"],
            payload["heartbeat"],
            payload["topics"],
            self._clock(),
        )
        self._vista.merge_digest(payload["peers"])

    def tick(self, now: float) -> None:
        self._vista.tick(now)
        if now < self._next_send:
            return

        self._heartbeat += 1
        self._next_send = now + self._interval
        sobre = cast(
            Sobre,
            {
                "tipo": "gossip",
                "from": self._transport.peer_id,
                "payload": {
                    "heartbeat": self._heartbeat,
                    "topics": self._vista.topics_de(self._vista.yo),
                    "peers": self._vista.digest(),
                },
            },
        )

        for objetivo in self._vista.elegir(self._rng, self._fanout):
            try:
                self._transport.send(objetivo, sobre)
            except (EndpointError, OSError) as error:
                logger.warning(
                    "no se pudo enviar gossip a %s: %s",
                    objetivo,
                    error,
                )

        logger.info(
            "[%s] heartbeat=%d vista=%d vivos=%d",
            self._transport.peer_id,
            self._heartbeat,
            len(self._vista),
            len(self._vista.vivos()),
        )
