"""Experimento de caida de peers (Seccion 5.3, paso 7).

Levanta un publicador y dos suscriptores que vuelcan metricas a la misma
carpeta. A mitad de la corrida se *apaga* (mata) uno de los suscriptores; el
estado de la vista del publicador debe pasar de vivo a muerto, y eso se ve en
las metricas y en el frontend (estado de la vista por peer).

Uso:
    python scripts/experimento_caida.py [--run-id run-caida]
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
from civicmesh.metrics import EscribirMetricas, leer_metricas
from civicmesh.node import Node
from civicmesh.pubsub import PoliticasCanales, PubSub
from civicmesh.transport import Transport

ROOT = Path(__file__).resolve().parents[1]
PUB_PEER = "127.0.0.1:7102"
T_SUSPECT = 2.0
T_DEAD = 4.0
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
    vista = MembershipView(peer_id, [PUB_PEER], t_suspect=T_SUSPECT, t_dead=T_DEAD)
    rng = random.Random(seed)
    gossip = Gossip(vista, transport, rng, fanout=1, interval=0.2)
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


def _linea_estado(metrics_dir: Path, peer: str) -> None:
    """Imprime la evolucion de vivos/sospechosos/muertos para el peer dado."""
    registros = [
        m
        for m in leer_metricas(metrics_dir)
        if m["kind"] == "state" and m["peer"] == peer
    ]
    if not registros:
        return
    ultimo = registros[-1]
    print(
        f"Estado final (peer {peer}): vivos={ultimo['vivos']} "
        f"sospechosos={ultimo['sospechosos']} muertos={ultimo['muertos']} "
        f"total={ultimo['total']}"
    )
    for reg in registros:
        print(
            f"  t={reg['ts']:9.4f}  vivos={reg['vivos']} "
            f"sospechosos={reg['sospechosos']} muertos={reg['muertos']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimento de caida de peers")
    parser.add_argument("--run-id", default="run-caida")
    parser.add_argument("--fase-alive", type=float, default=8.0)
    parser.add_argument("--fase-caida", type=float, default=10.0)
    parsed = parser.parse_args()

    run_id = parsed.run_id
    metrics_dir = ROOT / run_id / "metrics"

    # El publicador usa la config de publicadores.example.yaml (seed 7102 -> 7001).
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
        t_suspect=T_SUSPECT,
        t_dead=T_DEAD,
    )

    suscriptores = [
        _subscriber(f"127.0.0.1:{7000 + i}", 7000 + i, run_id, metrics_dir, 100 + i)
        for i in (1, 2)
    ]

    hilos = [threading.Thread(target=nodo_publicador.run, daemon=True)]
    hilos += [threading.Thread(target=sub.run, daemon=True) for sub in suscriptores]
    for hilo in hilos:
        hilo.start()

    print(f"Corriendo fase viva ({parsed.fase_alive}s) con 2 suscriptores...")
    threading.Event().wait(parsed.fase_alive)

    objetivo = suscriptores[-1]  # el segundo suscriptor no es el seed del publicador
    print(f"  >> MURIENDO peer {objetivo._transport.peer_id}")
    objetivo.stop()

    print(
        f"Esperando deteccion de fallo ({parsed.fase_caida}s, dead_after={T_DEAD}s)..."
    )
    threading.Event().wait(parsed.fase_caida)

    print("\n=== Estado de la vista (desde el publicador) ===")
    _linea_estado(metrics_dir, PUB_PEER)

    nodo_publicador.stop()
    for sub in suscriptores:
        sub.stop()
    for hilo in hilos:
        hilo.join(timeout=1.0)

    print(f"\nListo. Metricas en: {metrics_dir}")
    print(f"Frontend: python scripts/frontend.py --metrics {metrics_dir} --port 8080")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
