import json
import random
import socket
import time
from collections.abc import Sequence
from sys import argv

from civicmesh.membership.view import MembershipView


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
