"""Suscriptor de ejemplo que imprime en vivo los mensajes recibidos.

Permite verificar a mano que la capa Pub/Sub entrega los canales objetivo y
subjetivo. Se ejecuta junto con un publicador (civicmesh.domains.publisher_main):
el suscriptor se suscribe a una comuna y muestra cada mensaje que llega.

Uso:
    python scripts/verificar_pubsub.py --config config.example.yaml --peer peer-1 \
        --comuna santiago [--duracion 12.0]
"""

import argparse
import logging
import random
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from civicmesh.membership.gossip import Gossip
from civicmesh.membership.view import MembershipView
from civicmesh.node import Node, load_config
from civicmesh.pubsub import PubSub
from civicmesh.transport import Transport


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Suscriptor de verificacion de Pub/Sub"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--peer", required=True)
    parser.add_argument("--comuna", required=True)
    parser.add_argument("--duracion", type=float, default=12.0)
    parsed = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config(parsed.config, parsed.peer)

    transport = Transport(config.advertise, config.bind)
    vista = MembershipView(
        config.advertise,
        config.seeds,
        t_suspect=config.t_suspect,
        t_dead=config.t_dead,
    )
    rng = random.Random(config.random_seed)
    gossip = Gossip(
        vista,
        transport,
        rng,
        fanout=config.gossip_fanout,
        interval=config.gossip_interval,
    )
    pubsub = PubSub(vista, transport, config.pubsub_policies, rng=rng)
    pubsub.subscribe(parsed.comuna)

    conteo = {"objetivo": 0, "subjetivo": 0}

    def mostrar(mensaje: dict) -> None:
        canal = mensaje.get("channel", "?")
        conteo[canal] = conteo.get(canal, 0) + 1
        print(
            f"RECIBIDO [{canal}] {mensaje.get('topic')} -> "
            f"{mensaje.get('content')} ({mensaje.get('origin')})",
            flush=True,
        )

    pubsub.agregar_callback(mostrar)
    transport.register_handler("gossip", gossip.handle)
    transport.register_handler("pubsub", pubsub.handle)

    node = Node(transport, [gossip, pubsub], loop_interval=config.loop_interval)

    def cortar() -> None:
        threading.Event().wait(parsed.duracion)
        node.stop()

    hilo_corte = threading.Thread(target=cortar, daemon=True)
    hilo_corte.start()
    logging.info("suscriptor iniciado: comuna=%s", parsed.comuna)
    node.run()

    print(
        "Resumen: "
        f"objetivo={conteo.get('objetivo', 0)} "
        f"subjetivo={conteo.get('subjetivo', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
