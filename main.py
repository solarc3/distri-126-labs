import json
import random
import socket
import time
from sys import argv
from typing import Literal, TypedDict

# se agregan alias para tener un poquito de typechecking, asi si alguien escribe sospechoso o muerto en vez de eso, se rechaza
# constantes para definir sospecha de muerto y declarar muerto
T_SUSPECT = 10
T_DEAD = 20

Estado = Literal["alive", "suspect", "dead", "unknown"]


class PeerState(TypedDict):
    last_seen: float
    heartbeat: int
    estado: Estado


def endpoint(s: str) -> tuple[str, int]:
    h, p = s.split(":")
    return (h, int(p))


def addr_key(addr: tuple[str, int]) -> str:
    return f"{addr[0]}:{addr[1]}"


# socket.socket(family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# se usa INET pq requiere tener ip y puerto, AF_UNIX solo usa socket de linux
# se usa SOCK_DGRAM pq es UDP man 2 socket y man 7 udp, no creo que quieran implementar TCP y hacer framing para leer

puerto = int(argv[1])
semilla = argv[2]

sock.settimeout(0.2)
sock.bind(("0.0.0.0", puerto))

yo = f"127.0.0.1:{puerto}"
# el diccionario se va a usar para almacenar los destinos posibles, se debe poder ir actualizando
# la semilla es el unico peer que entra por argv; el resto entra por addr
# semilla
seen: dict[str, PeerState] = {
    semilla: {"last_seen": 0.0, "heartbeat": 0, "estado": "unknown"},
}


heartbeat = 0
while True:
    heartbeat += 1
    # el mensaje cambio, ahora se agrega el heartbeat de los peers para poder comparar ultima aparicion
    msg = {
        "from": puerto,
        "heartbeat": heartbeat,
        "peers": {p: v["heartbeat"] for p, v in seen.items()},
    }
    # dumps pasa de objeto a string, encode pasa string a bytes
    # object -> json string -> raw bytes
    msg_bytes = json.dumps(msg).encode()
    objetivo = random.choice(
        list(seen)
    )  # se selecciona target de manera random de seen
    sock.sendto(msg_bytes, endpoint(objetivo))

    while True:
        # def recvfrom(self, bufsize: int, flags: int = 0, /) -> tuple[bytes, _RetAddress]:
        try:
            data, addr = sock.recvfrom(65535)
        except TimeoutError:
            break

        remitente = addr_key((addr[0], addr[1]))
        recibido = json.loads(data.decode())

        # me escribe y lo agrego
        seen[remitente] = {
            "last_seen": time.monotonic(),
            "heartbeat": recibido["heartbeat"],
            "estado": "alive",
        }

        # recibo info y necesito confirmar
        vecinos = recibido["peers"]
        # se agrega el estado del heartbeat, pq sino se actualiza solo cuando uno lo ve recibe pero quiza otro nodo tiene algo mejor
        # podre tambien propagar el estado? aunq eso implica que existe federacion de info de un nodo a otros, no deberia existir jefatura, todos deben decidir que este muerto
        for v, hb in vecinos.items():
            if v == yo:
                continue
            if v not in seen:
                seen[v] = {"last_seen": 0.0, "heartbeat": hb, "estado": "unknown"}
            elif hb > seen[v]["heartbeat"]:
                seen[v]["heartbeat"] = hb

    ahora = time.monotonic()
    # se actualiza edad de los peers mediante last_seen
    # f"{destino[0]}:{destino[1]}"
    # si no esta en last seen se sigue
    # si la edad calculada es < sospechoso se updatea
    for p, v in seen.items():
        if not v["last_seen"]:
            continue
        edad = ahora - v["last_seen"]
        if edad < T_SUSPECT:
            v["estado"] = "alive"
        elif edad < T_DEAD:
            v["estado"] = "suspect"
        else:
            v["estado"] = "dead"

    print(f"[{puerto}] hb={heartbeat} vista={len(seen)}")
    for p, v in seen.items():
        edad = ahora - v["last_seen"] if v["last_seen"] else None
        edad_txt = f"{edad:5.1f}s" if edad is not None else "  n/a "
        print(f"   {p:22} hb={v['heartbeat']:<4} visto_hace={edad_txt} {v['estado']}")
    print()

    time.sleep(1)
