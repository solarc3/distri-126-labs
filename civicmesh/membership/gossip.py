import logging
import time
from collections.abc import Callable
from typing import TypeAlias, TypedDict, cast

from civicmesh.membership.view import MembershipView, RandomSource
from civicmesh.protocol import ProtocolError, Sobre
from civicmesh.transport import EndpointError, Transport, parse_endpoint

logger = logging.getLogger(__name__)

Clock: TypeAlias = Callable[[], float]


class GossipPayload(TypedDict):
    heartbeat: int
    peers: dict[str, int]


def _validar_payload_gossip(sobre: Sobre) -> GossipPayload:
    payload = sobre["payload"]
    campos_requeridos = {"heartbeat", "peers"}
    if not campos_requeridos.issubset(payload):
        raise ProtocolError("faltan campos obligatorios en el payload de gossip")

    heartbeat = payload["heartbeat"]
    if isinstance(heartbeat, bool) or not isinstance(heartbeat, int) or heartbeat < 0:
        raise ProtocolError("heartbeat debe ser un entero no negativo")

    peers = payload["peers"]
    if not isinstance(peers, dict):
        raise ProtocolError("peers debe ser un objeto JSON")

    for peer_id, peer_heartbeat in peers.items():
        try:
            parse_endpoint(peer_id)
        except EndpointError as error:
            raise ProtocolError(f"peer ID invalido en digest: {peer_id}") from error

        if (
            isinstance(peer_heartbeat, bool)
            or not isinstance(peer_heartbeat, int)
            or peer_heartbeat < 0
        ):
            raise ProtocolError(f"heartbeat invalido para peer {peer_id}")

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
