"""Graficos del informe a partir de las metricas (Seccion 8).

Lee un directorio de metricas (topic x canal), grafica la convergencia del canal
objetivo (dispersion entre peers en el tiempo) y la brecha percepcion-realidad,
y muestra un resumen estadistico (incluye el gap relativo para comparar dominios
con unidades distintas: µg/m3 en aire vs. conteo en delitos).

Uso:
    python scripts/graficos_informe.py --metrics run-cmp/aire/metrics \
        --etiqueta aire --outdir graficos
"""

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from civicmesh.metrics import (
    brecha_percepcion,
    convergencia,
    leer_metricas,
    serie_topic,
)

ROOT = Path(__file__).resolve().parents[1]


def _grafica_convergencia(serie, eps, out, etiqueta) -> None:
    xs = [ventana for ventana, _spread, _desv, _n in serie]
    ys = [spread for _ventana, spread, _desv, _n in serie]
    fig, ax = plt.subplots()
    ax.plot(xs, ys, marker="o", label="dispersion (max-min)")
    ax.axhline(eps, color="red", linestyle="--", label=f"eps={eps}")
    ax.set_title(f"Convergencia objetivo - {etiqueta}")
    ax.set_xlabel("t (s)")
    ax.set_ylabel("Dispersion entre peers")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def _grafica_brecha(brechas, out, etiqueta) -> None:
    peers = sorted({p for _t, p, _g in brechas})
    fig, ax = plt.subplots()
    for peer in peers:
        xs = [t for t, p, _g in brechas if p == peer]
        ys = [g for t, p, g in brechas if p == peer]
        ax.plot(xs, ys, marker=".", label=peer)
    ax.axhline(0, color="gray", linestyle=":")
    ax.set_title(f"Brecha percepcion-realidad - {etiqueta}")
    ax.set_xlabel("t (s)")
    ax.set_ylabel("gap (subjetivo - objetivo)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def _etiqueta_unidad(dominio: str) -> str:
    return "(ug/m3)" if dominio == "aire" else "(eventos)"


def main(
    outdir: Path,
    metrics_dir: Path,
    etiqueta: str,
    topic: str,
    eps: float,
    bucket: float,
) -> None:
    metricas = list(leer_metricas(metrics_dir))
    conv = convergencia(metricas, topic, "objetivo", eps, bucket)
    brechas = brecha_percepcion(metricas, topic)
    valores_objetivo = [v for _t, _p, v in serie_topic(metricas, topic, "objetivo")]
    gaps_abs = [abs(g) for _t, _p, g in brechas]

    outdir.mkdir(parents=True, exist_ok=True)
    _grafica_convergencia(
        conv.serie, eps, outdir / f"convergencia_{etiqueta}.png", etiqueta
    )
    _grafica_brecha(brechas, outdir / f"brecha_{etiqueta}.png", etiqueta)

    objetivo_medio = statistics.fmean(valores_objetivo) if valores_objetivo else 0.0
    mean_abs = statistics.fmean(gaps_abs) if gaps_abs else 0.0
    gap_relativo = (mean_abs / objetivo_medio) if objetivo_medio else float("nan")

    print(f"\n=== {etiqueta} ===")
    print(f"  Graficos: {outdir / ('convergencia_' + etiqueta + '.png')}")
    print(f"           {outdir / ('brecha_' + etiqueta + '.png')}")
    print(
        f"  Convergio: {'SI' if conv.convergido else 'NO'} (dispersion final="
        f"{conv.dispersion_final:.3f}, ts={conv.ts_convergencia})"
    )
    print(f"  Muestras objetivo: {len(valores_objetivo)} | Brechas: {len(brechas)}")
    print(f"  Objetivo medio: {objetivo_medio:.3f} {_etiqueta_unidad(etiqueta)}")
    print(f"  Media |gap|: {mean_abs:.3f} {_etiqueta_unidad(etiqueta)}")
    print(f"  Gap relativo (media|gap| / objetivo_medio): {gap_relativo:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Graficos del informe")
    parser.add_argument(
        "--metrics",
        type=Path,
        required=True,
        help="directorio de metricas (el que usa el frontend)",
    )
    parser.add_argument("--etiqueta", required=True, help="aire o delitos")
    parser.add_argument("--outdir", type=Path, default=ROOT / "graficos")
    parser.add_argument("--topic", default="santiago")
    parser.add_argument("--eps", type=float, default=2.0)
    parser.add_argument("--bucket", type=float, default=0.5)
    parsed = parser.parse_args()
    main(
        parsed.outdir,
        parsed.metrics,
        parsed.etiqueta,
        parsed.topic,
        parsed.eps,
        parsed.bucket,
    )
