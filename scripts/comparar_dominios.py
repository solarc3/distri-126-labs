"""Comparacion estadistica entre dominios (Seccion 4.4).

Corre un publicador y dos suscriptores en el Dominio B (aire, señal continua
con replay) y luego en el Dominio A (delitos, eventos discretos por Poisson).
Para cada dominio mide la convergencia del canal objetivo y la brecha
percepcion-realidad, y guarda una tabla comparativa CSV.

Uso:
    python scripts/comparar_dominios.py [--duracion 12] [--run-id run-cmp]
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
POLITICAS: PoliticasCanales = {
    "objetivo": {"ttl": 5, "priority": 2},
    "subjetivo": {"ttl": 3, "priority": 1},
}
T_SUSPECT = 5.0
T_DEAD = 10.0


def _subscriber(
    dominio: str,
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
    pubsub.subscribe(TOPIC)
    escritor = EscribirMetricas(run_id, peer_id, metrics_dir)
    acumulado = [0.0]

    def _registrar(mensaje: dict) -> None:
        canal = mensaje.get("channel")
        contenido = mensaje.get("content")
        if not isinstance(contenido, dict) or not canal:
            return
        if canal == "objetivo":
            if dominio == "aire":
                valor = contenido.get("pm2_5")
                if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                    escritor.topic(dominio, TOPIC, "objetivo", float(valor))
            else:
                conteo = contenido.get("count")
                if isinstance(conteo, (int, float)) and not isinstance(conteo, bool):
                    acumulado[0] += float(conteo)
        elif canal == "subjetivo":
            valor = contenido.get("value")
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                if dominio == "delitos":
                    escritor.topic(dominio, TOPIC, "objetivo", acumulado[0])
                    acumulado[0] = 0.0
                escritor.topic(dominio, TOPIC, "subjetivo", float(valor))

    pubsub.agregar_callback(_registrar)
    transport.register_handler("gossip", gossip.handle)
    transport.register_handler("pubsub", pubsub.handle)
    return Node(transport, [gossip, pubsub], loop_interval=0.01)


def _correr_dominio(dominio: str, run_id: str, duracion: float) -> dict:
    metrics_dir = ROOT / run_id / dominio / "metrics"
    nodo_publicador = build_publisher_node(
        ROOT / "publicadores.example.yaml",
        "publicador-aire-1",
        ROOT / "generadores.example.yaml",
        dominio,
        TOPIC,
        ROOT / "data" / "air_quality",
        intervalo_segundos=0.4,
        loop_air=True,
        run_id=run_id,
        metrics_dir=metrics_dir,
        t_suspect=T_SUSPECT,
        t_dead=T_DEAD,
    )
    suscriptores = [
        _subscriber(
            dominio, f"127.0.0.1:{7000 + i}", 7000 + i, run_id, metrics_dir, 100 + i
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
    convergencia = objetivo.get("convergencia", {})
    brecha = tema.get("brecha", [])

    gaps = [abs(g) for _t, _p, g in brecha]
    return {
        "dominio": dominio,
        "convergio": bool(convergencia.get("convergido")),
        "dispersion_final": convergencia.get("dispersion_final"),
        "muestras_objetivo": len(objetivo.get("serie", [])),
        "n_gap": len(gaps),
        "mean_abs_gap": statistics.fmean(gaps) if gaps else 0.0,
        "min_abs_gap": min(gaps) if gaps else 0.0,
        "max_abs_gap": max(gaps) if gaps else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparacion delitos vs aire")
    parser.add_argument("--duracion", type=float, default=12.0)
    parser.add_argument("--run-id", default="run-cmp")
    parsed = parser.parse_args()

    resultados = [
        _correr_dominio(dominio, parsed.run_id, parsed.duracion)
        for dominio in ("aire", "delitos")
    ]

    encabezado = [
        "dominio",
        "convergio",
        "dispersion_final",
        "mean_abs_gap",
        "max_abs_gap",
    ]
    print("\n=== Comparacion Dominio A (delitos) vs Dominio B (aire) ===")
    for r in resultados:
        print(
            f"  {r['dominio']:8s}  convergio={'SI' if r['convergio'] else 'NO':2s}  "
            f"disp={r['dispersion_final']:5.2f}  media|gap|={r['mean_abs_gap']:7.3f}  "
            f"max|gap|={r['max_abs_gap']:7.3f}  n={r['n_gap']}"
        )

    csv_path = ROOT / parsed.run_id / "comparacion.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8") as f:
        f.write(",".join(encabezado) + "\n")
        for r in resultados:
            f.write(
                f"{r['dominio']},{int(r['convergio'])},"
                f"{r['dispersion_final']},{r['mean_abs_gap']},{r['max_abs_gap']}\n"
            )
    print(f"\nTabla CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
