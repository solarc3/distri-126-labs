import json
import random
import socket
import time
from sys import argv


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
host, port = argv[2].split(":")
destino = (host, int(port))

sock.settimeout(0.2)
sock.bind(("0.0.0.0", puerto))

# se asume que no se usa DNS, string print de ips para evitar localhost
yo = f"{destino[0]}:{puerto}" if destino[0] != host else f"127.0.0.1:{puerto}"

seen = {}
# el diccionario se va a usar para almacenar los destinos posibles, se debe poder ir actualizando
# la semilla es el unico peer que entra por argv; el resto entra por addr
seen[f"{destino[0]}:{destino[1]}"] = time.monotonic()
heartbeat = 0
while True:
    heartbeat += 1
    msg = {"from": puerto, "heartbeat": heartbeat, "peers": list(seen)}
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
        # facil hacer el string print pero nose si sea lo mejor para guardar como llave, quiza conviene mas hacer getaddrinfo y dejar eso como llave? en vez de andar haciendo hacks con strings, por algo existe y se podria aprovechar, pq ahora se serializa como un any y que fome intentar buscar que es
        seen[remitente] = time.monotonic()
        vecinos = json.loads(data.decode())["peers"]
        # ya teniendo la lista de vecinos de alguien que me la manda, se revisa contra la mia y se actualiza en caso de ser necesario
        for v in vecinos:
            if yo != v and v not in seen:
                seen[v] = time.monotonic()

    time.sleep(1)
