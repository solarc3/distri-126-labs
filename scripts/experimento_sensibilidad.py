"""Sensibilidad del canal objetivo al TTL (Seccion 4.4).

Para cada TTL, levanta un publicador de aire y dos suscriptores de la misma
comuna que vuelcan lo que reciben. Se mide si los suscriptores logran el valor
objetivo (convergencia) y la brecha perceptiva. Con TTL muy bajo el publicador
no reenvía y el ground truth no llega: la convergencia deja de darse.

Uso:
    python scripts/experimento_sensibilidad.py [--duracion 10] [--run-id run-sens]
"""

import argparse
import random
import statistics
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from civicmesh.domains.publisher_main import build_publisher_node
from civicmesh.frontend import construir_resumen
from civicmesh.membership.gossip import Gossip
from civicmesh.membership.view import MembershipView
from civicmesh.metrics import EscribirMetricas, leer_metricas
from civicmesh.node import Node
from civicmesh.pubsub import PoliticasCanales, PubSub
from civicmesh.transport import Transport

ROOT = Path(__file__).resolve().parents[1]
PUB_PEER = "127.0.0.1:7102"
TOPIC = "santiago"
T_SUSPECT = 5.0
T_DEAD = 10.0
TTLS = (1, 2, 5)


def _politicas(ttl_objetivo: int) -> PoliticasCanales:
    return {
        "objetivo": {"ttl": ttl_objetivo, "priority": 2},
        "subjetivo": {"ttl": 3, "priority": 1},
    }


def _subscriber(
    peer_id: str,
    puerto: int,
    run_id: str,
    metrics_dir: Path,
    seed: int,
    politicas: PoliticasCanales,
) -> Node:
    transport = Transport(peer_id, ("127.0.0.1", puerto))
    vista = MembershipView(peer_id, [PUB_PEER], t_suspect=T_SUSPECT, t_dead=T_DEAD)
    rng = random.Random(seed)
    gossip = Gossip(vista, transport, rng, fanout=1, interval=0.2)
    pubsub = PubSub(vista, transport, politicas, rng=rng)
    pubsub.subscribe(TOPIC)
    escritor = EscribirMetricas(run_id, peer_id, metrics_dir)

    def _registrar(mensaje: dict) -> None:
        canal = mensaje.get("channel")
        contenido = mensaje.get("content")
        if not isinstance(contenido, dict) or not canal:
            return
        if canal == "objetivo":
            valor = contenido.get("pm2_5")
        else:
            valor = contenido.get("value")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            escritor.topic("aire", TOPIC, canal, float(valor))

    pubsub.agregar_callback(_registrar)
    transport.register_handler("gossip", gossip.handle)
    transport.register_handler("pubsub", pubsub.handle)
    return Node(transport, [gossip, pubsub], loop_interval=0.01)


def _correr_ttl(ttl: int, run_id: str, duracion: float) -> dict:
    politicas = _politicas(ttl)
    metrics_dir = ROOT / run_id / f"ttl{ttl}" / "metrics"
    nodo_publicador = build_publisher_node(
        ROOT / "publicadores.example.yaml",
        "publicador-aire-1",
        ROOT / "generadores.example.yaml",
        "aire",
        TOPIC,
        ROOT / "data" / "air_quality",
        intervalo_segundos=0.4,
        loop_air=True,
        run_id=run_id,
        metrics_dir=metrics_dir,
        t_suspect=T_SUSPECT,
        t_dead=T_DEAD,
        politicas=politicas,
    )
    suscriptores = [
        _subscriber(
            f"127.0.0.1:{7000 + i}", 7000 + i, run_id, metrics_dir, 100 + i, politicas
        )
        for i in (1, 2)
    ]
    hilos = [threading.Thread(target=nodo_publicador.run, daemon=True)]
    hilos += [threading.Thread(target=sub.run, daemon=True) for sub in suscriptores]
    for hilo in hilos:
        hilo.start()

    threading.Event().wait(duracion)

    nodo_publicador.stop()
    for sub in suscriptores:
        sub.stop()
    for hilo in hilos:
        hilo.join(timeout=1.0)

    resumen = construir_resumen(list(leer_metricas(metrics_dir)))
    tema = resumen["topicos"].get(TOPIC, {})
    objetivo = tema.get("objetivo", {})
    conv = objetivo.get("convergencia", {})
    gaps = [abs(g) for _t, _p, g in tema.get("brecha", [])]
    peers_objetivo = {peer for _t, peer, _v in objetivo.get("serie", [])}
    return {
        "ttl": ttl,
        "convergio": bool(conv.get("convergido")),
        "dispersion_final": conv.get("dispersion_final"),
        "muestras_objetivo": len(objetivo.get("serie", [])),
        "peers_objetivo": len(peers_objetivo),
        "mean_abs_gap": statistics.fmean(gaps) if gaps else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sensibilidad al TTL del objetivo")
    parser.add_argument("--duracion", type=float, default=10.0)
    parser.add_argument("--run-id", default="run-sens")
    parsed = parser.parse_args()

    print("=== Sensibilidad del canal objetivo al TTL ===")
    resultados = [_correr_ttl(ttl, parsed.run_id, parsed.duracion) for ttl in TTLS]
    for r in resultados:
        print(
            f"  ttl={r['ttl']}  convergio={'SI' if r['convergio'] else 'NO':2s}  "
            f"peers_objetivo={r['peers_objetivo']}/3  "
            f"muestras_objetivo={r['muestras_objetivo']:4d}  "
            f"media|gap|={r['mean_abs_gap']:7.3f}"
        )

    csv_path = ROOT / parsed.run_id / "sensibilidad.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8") as f:
        f.write("ttl,convergio,peers_objetivo,muestras_objetivo,mean_abs_gap\n")
        for r in resultados:
            f.write(
                f"{r['ttl']},{int(r['convergio'])},{r['peers_objetivo']},"
                f"{r['muestras_objetivo']},{r['mean_abs_gap']}\n"
            )
    print(f"\nTabla CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
