"""Demo de convergencia entre peers.

Levanta 1 publicador de aire (santiago) y N suscriptores de la misma comuna.
Cada peer es un nodo completo con su propio socket UDP y bucle de gossip; todos
vuelcan a la misma carpeta de metricas. Asi el frontend puede calcular la
dispersion entre peers del canal objetivo y mostrar la convergencia real.

Uso:
    python scripts/verificar_convergencia.py [--suscriptores 2] [--duracion 15]
"""

import argparse
import random
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from civicmesh.domains.publisher_main import build_publisher_node
from civicmesh.membership.gossip import Gossip
from civicmesh.membership.view import MembershipView
from civicmesh.metrics import EscribirMetricas
from civicmesh.node import Node
from civicmesh.pubsub import PoliticasCanales, PubSub
from civicmesh.transport import Transport

ROOT = Path(__file__).resolve().parents[1]
PUB_PEER = "127.0.0.1:7102"
POLITICAS: PoliticasCanales = {
    "objetivo": {"ttl": 5, "priority": 2},
    "subjetivo": {"ttl": 3, "priority": 1},
}


def _subscriber(
    peer_id: str,
    puerto: int,
    run_id: str,
    metrics_dir: Path,
    seed: int,
) -> Node:
    transport = Transport(peer_id, ("127.0.0.1", puerto))
    vista = MembershipView(peer_id, [PUB_PEER], t_suspect=10, t_dead=20)
    rng = random.Random(seed)
    gossip = Gossip(vista, transport, rng, fanout=1, interval=0.1)
    pubsub = PubSub(vista, transport, POLITICAS, rng=rng)
    pubsub.subscribe("santiago")
    escritor = EscribirMetricas(run_id, peer_id, metrics_dir)

    def _registrar(mensaje: dict) -> None:
        canal = mensaje.get("channel")
        contenido = mensaje.get("content")
        if not isinstance(contenido, dict):
            return
        valor = (
            contenido.get("pm2_5") if canal == "objetivo" else contenido.get("value")
        )
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            escritor.topic("aire", "santiago", canal, float(valor))

    pubsub.agregar_callback(_registrar)
    transport.register_handler("gossip", gossip.handle)
    transport.register_handler("pubsub", pubsub.handle)
    return Node(transport, [gossip, pubsub], loop_interval=0.01)


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo de convergencia entre peers")
    parser.add_argument("--suscriptores", type=int, default=2)
    parser.add_argument("--duracion", type=float, default=15.0)
    parser.add_argument("--run-id", default="run-conv")
    parsed = parser.parse_args()

    if parsed.suscriptores < 1:
        parser.error("suscriptores debe ser al menos 1")

    run_id = parsed.run_id
    metrics_dir = ROOT / run_id / "metrics"

    nodo_publicador = build_publisher_node(
        ROOT / "publicadores.example.yaml",
        "publicador-aire-1",
        ROOT / "generadores.example.yaml",
        "aire",
        "santiago",
        ROOT / "data" / "air_quality",
        intervalo_segundos=0.4,
        loop_air=True,
        run_id=run_id,
        metrics_dir=metrics_dir,
    )

    suscriptores = [
        _subscriber(
            f"127.0.0.1:{7000 + i}",
            7000 + i,
            run_id,
            metrics_dir,
            seed=100 + i,
        )
        for i in range(1, parsed.suscriptores + 1)
    ]

    hilos = [threading.Thread(target=nodo_publicador.run, daemon=True)]
    hilos += [threading.Thread(target=sub.run, daemon=True) for sub in suscriptores]
    for hilo in hilos:
        hilo.start()

    print(f"Corriendo {parsed.duracion}s con {parsed.suscriptores} suscriptores...")
    print(f"Metricas en: {metrics_dir}")
    threading.Event().wait(parsed.duracion)

    nodo_publicador.stop()
    for sub in suscriptores:
        sub.stop()
    for hilo in hilos:
        hilo.join(timeout=1.0)

    print(f"Listo. Abrí el frontend con la carpeta: {metrics_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
