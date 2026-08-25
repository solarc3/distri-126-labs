"""Demo del contrato de métricas de CivicMesh.

Genera una corrida sintetica (objetivo/subjetivo, estado de la vista y
estadisticas de red) en ``metrics/`` y aplica las funciones de agregacion,
imprimiendo las tres vistas que consume el frontend (Seccion 5.4):

  (i)  estado por topic x canal
  (ii) brecha percepcion-realidad
  (iii) convergencia entre peers

Uso:
    python scripts/demo_metrics.py [directorio_destino]
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from civicmesh.metrics import (
    EscribirMetricas,
    brecha_percepcion,
    convergencia,
    leer_metricas,
    serie_topic,
    ultimo_valor,
)


def _demo(directorio: Path) -> None:
    base = directorio / "metrics"
    run_id = "demo-local-001"
    peers = ("127.0.0.1:7001", "127.0.0.1:7002")
    escritores = {peer: EscribirMetricas(run_id, peer, base) for peer in peers}

    for paso, (objetivo_a, objetivo_b) in enumerate(
        ((25.0, 40.0), (30.0, 30.0)),
        start=1,
    ):
        t = 100.0 + paso * 2
        escritores[peers[0]].topic("aire", "santiago", "objetivo", objetivo_a, ts=t)
        escritores[peers[1]].topic("aire", "santiago", "objetivo", objetivo_b, ts=t)

    for paso, (subjetivo_a, subjetivo_b) in enumerate(
        ((38.0, 45.0), (33.0, 33.0)),
        start=1,
    ):
        t = 100.5 + paso * 2
        escritores[peers[0]].topic("aire", "santiago", "subjetivo", subjetivo_a, ts=t)
        escritores[peers[1]].topic("aire", "santiago", "subjetivo", subjetivo_b, ts=t)

    escritores[peers[0]].estado(2, 0, 0, 2, ts=100.0)
    escritores[peers[1]].estado(2, 0, 0, 2, ts=100.0)
    escritores[peers[0]].estado(1, 0, 1, 2, ts=105.0)
    escritores[peers[0]].red(12, 8, 3, ts=100.0)

    metricas = list(leer_metricas(base))

    print(f"Run: {run_id}")
    print(f"== Registros leidos: {len(metricas)} ==")
    print()

    print("(i) Estado actual por peer (objetivo):")
    print("   ", ultimo_valor(metricas, "santiago", "objetivo"))
    print()

    print("(i) Serie objetivo (ts, peer, valor):")
    for item in serie_topic(metricas, "santiago", "objetivo"):
        print("   ", item)
    print()

    print("(ii) Brecha percepcion-realidad (ts, peer, P - v):")
    for item in brecha_percepcion(metricas, "santiago"):
        print("   ", item)
    print()

    print("(iii) Convergencia del objetivo (bucket=1s, eps=2):")
    resumen = convergencia(metricas, "santiago", "objetivo", eps=2.0, bucket=1.0)
    for ventana, spread, desviacion, cantidad in resumen.serie:
        print(
            f"    t={ventana:5.1f}  spread={spread:5.1f}  "
            f"desv={desviacion:5.1f}  peers={cantidad}"
        )
    print("    convergido:", resumen.convergido)
    print("    ts_convergencia:", resumen.ts_convergencia)


def _main(args: list[str]) -> int:
    if args:
        destino = Path(args[0])
        destino.mkdir(parents=True, exist_ok=True)
    else:
        destino = Path(tempfile.mkdtemp(prefix="civicmesh-demo-"))
    _demo(destino)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
