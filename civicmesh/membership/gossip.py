import json
import random
import socket
import time
from collections.abc import Callable, Sequence
from sys import argv
from typing import TypeAlias, TypedDict, cast

from civicmesh.membership.view import MembershipView, RandomSource
from civicmesh.protocol import ProtocolError, Sobre
from civicmesh.transport import EndpointError, Transport, parse_endpoint

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


def endpoint(s: str) -> tuple[str, int]:
    h, p = s.split(":")
    return (h, int(p))


def addr_key(addr: tuple[str, int]) -> str:
    return f"{addr[0]}:{addr[1]}"


def main(args: Sequence[str] | None = None) -> None:
    if args is None:
        args = argv

    puerto = int(args[1])
    semilla = args[2]

    # socket.socket(family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # se usa INET pq requiere tener ip y puerto, AF_UNIX solo usa socket de linux
    # se usa SOCK_DGRAM pq es UDP man 2 socket y man 7 udp, no creo que quieran
    # implementar TCP y hacer framing para leer
    sock.settimeout(0.2)
    sock.bind(("0.0.0.0", puerto))

    yo = f"127.0.0.1:{puerto}"
    vista = MembershipView(yo, semilla, t_suspect=10, t_dead=20)
    rng = random.Random()

    heartbeat = 0
    while True:
        heartbeat += 1
        # el mensaje cambio, ahora se agrega el heartbeat de los peers para poder
        # comparar ultima aparicion
        msg = {
            "from": puerto,
            "heartbeat": heartbeat,
            "peers": vista.digest(),
        }
        # dumps pasa de objeto a string, encode pasa string a bytes
        # object -> json string -> raw bytes
        msg_bytes = json.dumps(msg).encode()
        for objetivo in vista.elegir(rng, 1):
            # se selecciona target de manera random de seen
            sock.sendto(msg_bytes, endpoint(objetivo))

        while True:
            # def recvfrom(self, bufsize: int, flags: int = 0, /)
            # -> tuple[bytes, _RetAddress]:
            try:
                data, addr = sock.recvfrom(65535)
            except TimeoutError:
                break

            remitente = addr_key((addr[0], addr[1]))
            recibido = json.loads(data.decode())

            # me escribe y lo agrego
            vista.contacto_directo(
                remitente,
                recibido["heartbeat"],
                time.monotonic(),
            )
            vista.merge_digest(recibido["peers"])

        ahora = time.monotonic()
        vista.tick(ahora)

        print(f"[{puerto}] hb={heartbeat} vista={len(vista)}")
        for pid, estado_peer in vista.items():
            last_seen = estado_peer["last_seen"]
            edad = ahora - last_seen if last_seen else None
            edad_txt = f"{edad:5.1f}s" if edad is not None else "  n/a "
            print(
                f"   {pid:22} hb={estado_peer['heartbeat']:<4} "
                f"visto_hace={edad_txt} {estado_peer['estado']}"
            )
        print()

        time.sleep(1)


if __name__ == "__main__":
    main()
