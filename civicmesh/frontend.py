"""Construcción del resumen que consume el frontend de estadísticas.

Sección 5.4 del informe: el frontend debe mostrar el estado por topic y canal,
la brecha percepcion-realidad del canal subjetivo y la convergencia entre peers.
Esta capa no depende de ningún framework web: transforma las métricas en un
diccionario JSON-serializable que cualquier frontend puede graficar.
"""

from collections.abc import Iterable, Sequence
from typing import TypeAlias

from civicmesh.metrics import (
    CanalMetrica,
    Metrica,
    brecha_percepcion,
    convergencia,
    serie_topic,
    ultimo_valor,
)

Resumen: TypeAlias = dict[str, object]


def topics_medidos(metricas: Sequence[Metrica]) -> set[str]:
    return {m["topic"] for m in metricas if m["kind"] == "topic"}


def canales_medidos(metricas: Sequence[Metrica], topic: str) -> set[CanalMetrica]:
    canales: set[CanalMetrica] = set()
    for m in metricas:
        if m["kind"] == "topic" and m["topic"] == topic:
            canales.add(m["channel"])
    return canales


def _vista_estado(metricas: Sequence[Metrica]) -> dict[str, dict[str, int]]:
    ultima: dict[str, dict[str, int]] = {}
    ultimo_ts: dict[str, float] = {}
    for m in metricas:
        if m["kind"] != "state":
            continue
        previo = ultimo_ts.get(m["peer"])
        if previo is not None and m["ts"] < previo:
            continue
        ultimo_ts[m["peer"]] = m["ts"]
        ultima[m["peer"]] = {
            "vivos": m["vivos"],
            "sospechosos": m["sospechosos"],
            "muertos": m["muertos"],
            "total": m["total"],
        }
    return ultima


def construir_resumen(
    metricas: Iterable[Metrica],
    *,
    eps: float = 2.0,
    bucket: float = 0.1,
) -> Resumen:
    """Arma el resumen JSON con tópicos, brechas, vista y estadísticas en vivo."""
    lista = list(metricas)
    topicos: dict[str, dict[str, object]] = {}

    for topic in sorted(topics_medidos(lista)):
        entrada: dict[str, object] = {}
        for canal in sorted(canales_medidos(lista, topic), reverse=True):
            serie = serie_topic(lista, topic, canal)
            resumen_canal = convergencia(lista, topic, canal, eps, bucket)
            entrada[canal] = {
                "serie": [[ts, peer, valor] for ts, peer, valor in serie],
                "ultimo_por_peer": ultimo_valor(lista, topic, canal),
                "convergencia": {
                    "convergido": resumen_canal.convergido,
                    "ts_convergencia": resumen_canal.ts_convergencia,
                    "dispersion_final": resumen_canal.dispersion_final,
                    "serie": [
                        [ventana, spread, desviacion, cantidad]
                        for ventana, spread, desviacion, cantidad in resumen_canal.serie
                    ],
                },
            }
        entrada["brecha"] = [
            [ts, peer, gap] for ts, peer, gap in brecha_percepcion(lista, topic)
        ]
        topicos[topic] = entrada

    return {
        "total_registros": len(lista),
        "topicos": topicos,
        "vista": _vista_estado(lista),
    }
