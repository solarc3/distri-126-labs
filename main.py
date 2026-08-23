import json
import socket
import time
from sys import argv

# socket.socket(family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# se usa INET pq requiere tener ip y puerto, AF_UNIX solo usa socket de linux
# se usa SOCK_DGRAM pq es UDP man 2 socket y man 7 udp, no creo que quieran implementar TCP y hacer framing para leer
puerto = int(argv[1])
host, port = argv[2].split(":")
destino = (host, int(port))
sock.settimeout(0.2)
sock.bind(("localhost", puerto))

heartbeat = 0

while True:
    heartbeat += 1
    msg = {"from": puerto, "heartbeat": heartbeat}
    # dumps pasa de objeto a string, encode pasa string a bytes
    # object -> json string -> raw bytes
    msg_bytes = json.dumps(msg).encode()
    sock.sendto(msg_bytes, destino)

    while True:
        # def recvfrom(self, bufsize: int, flags: int = 0, /) -> tuple[bytes, _RetAddress]:
        try:
            data, addr = sock.recvfrom(65535)
        except:
            print("algo exploto y no pude recibir info")
            break
        print("hola soy la info que llega y la direccion \n")
        payload = data
        print(data)
        print(addr)
    time.sleep(1)
