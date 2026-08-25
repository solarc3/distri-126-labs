"""Registro y agregación de métricas experimentales de CivicMesh.

El contrato de métricas alimenta el frontend (Sección 5.4 del informe), que
debe mostrar el estado por topic x canal, la brecha percepción-realidad y la
convergencia entre peers. Cada registro es una línea JSON en ``metrics/``.
"""

import json
import math
import statistics
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias, TypedDict, cast

CanalMetrica: TypeAlias = Literal["objetivo", "subjetivo"]
TipoMetrica: TypeAlias = Literal["topic", "state", "network"]
EXTENSION_JSONL = ".jsonl"

CAMPOS_COMUNES = ("kind", "run_id", "ts", "peer")
CAMPOS_TOPIC = ("domain", "topic", "channel", "value")
CAMPOS_STATE = ("vivos", "sospechosos", "muertos", "total")
CAMPOS_NETWORK = ("enviados", "reenviados", "descartados_ttl")


class MetricaTopic(TypedDict):
    kind: Literal["topic"]
    run_id: str
    ts: float
    peer: str
    domain: str
    topic: str
    channel: CanalMetrica
    value: float


class MetricaEstado(TypedDict):
    kind: Literal["state"]
    run_id: str
    ts: float
    peer: str
    vivos: int
    sospechosos: int
    muertos: int
    total: int


class MetricaRed(TypedDict):
    kind: Literal["network"]
    run_id: str
    ts: float
    peer: str
    enviados: int
    reenviados: int
    descartados_ttl: int


Metrica: TypeAlias = MetricaTopic | MetricaEstado | MetricaRed


class MetricaError(ValueError):
    """Indica que una línea de métricas no cumple el contrato."""


def saludar_peer_id(peer_id: str) -> str:
    """Convierte un peer ID host:puerto en un nombre de archivo seguro."""
    return peer_id.replace(":", "_").replace(".", "_").replace("/", "_")


def _exigir(
    registro: dict[object, object],
    campo: str,
    tipo: type | tuple[type, ...],
) -> object:
    valor = registro.get(campo)
    if valor is None and campo in registro:
        raise MetricaError(f"el campo {campo} no puede ser nulo")
    if not isinstance(valor, tipo):
        raise MetricaError(f"el campo {campo} debe ser {tipo.__name__}")
    return valor


def _exigir_campos(registro: dict[object, object], campos: tuple[str, ...]) -> None:
    for campo in campos:
        if campo not in registro:
            raise MetricaError(f"falta el campo {campo}")


def _validar_registro(registro: object) -> Metrica:
    if not isinstance(registro, dict):
        raise MetricaError("cada línea de métricas debe ser un objeto")

    _exigir_campos(registro, CAMPOS_COMUNES)
    kind = _exigir(registro, "kind", str)
    _exigir(registro, "run_id", str)
    _exigir(registro, "ts", (float, int))
    _exigir(registro, "peer", str)

    if kind == "topic":
        _exigir_campos(registro, CAMPOS_TOPIC)
        if registro["channel"] not in ("objetivo", "subjetivo"):
            raise MetricaError(
                "el canal de un registro topic debe ser objetivo/subjetivo"
            )
        _exigir(registro, "value", (float, int))
    elif kind == "state":
        _exigir_campos(registro, CAMPOS_STATE)
        for campo in CAMPOS_STATE:
            _exigir(registro, campo, (int, float))
    elif kind == "network":
        _exigir_campos(registro, CAMPOS_NETWORK)
        for campo in CAMPOS_NETWORK:
            _exigir(registro, campo, (int, float))
    else:
        raise MetricaError(f"kind desconocido: {kind}")

    return cast(Metrica, registro)


class EscribirMetricas:
    """Escribe líneas JSON en un archivo por peer dentro de ``metrics/``."""

    def __init__(self, run_id: str, peer: str, directorio: Path) -> None:
        self.run_id = run_id
        self.peer = peer
        self._archivo = (
            directorio / f"metricas-{saludar_peer_id(peer)}{EXTENSION_JSONL}"
        )

    def _escribir(self, registro: dict[str, object]) -> None:
        registro.setdefault("run_id", self.run_id)
        registro.setdefault("peer", self.peer)
        ts = registro.get("ts")
        if ts is None or ts == 0.0:
            registro["ts"] = time.time()
        self._archivo.parent.mkdir(parents=True, exist_ok=True)
        with self._archivo.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")

    def registrar(self, metrica: Metrica, ts: float | None = None) -> None:
        """Vuelca una métrica ya construida; permite fijar el instante."""
        registro: dict[str, object] = dict(metrica)
        if ts is not None:
            registro["ts"] = ts
        self._escribir(registro)

    def topic(
        self,
        domain: str,
        topic: str,
        channel: CanalMetrica,
        value: float,
        ts: float | None = None,
    ) -> None:
        self.registrar(
            {
                "kind": "topic",
                "run_id": self.run_id,
                "ts": 0.0,
                "peer": self.peer,
                "domain": domain,
                "topic": topic,
                "channel": channel,
                "value": value,
            },
            ts,
        )

    def estado(
        self,
        vivos: int,
        sospechosos: int,
        muertos: int,
        total: int,
        ts: float | None = None,
    ) -> None:
        self.registrar(
            {
                "kind": "state",
                "run_id": self.run_id,
                "ts": 0.0,
                "peer": self.peer,
                "vivos": vivos,
                "sospechosos": sospechosos,
                "muertos": muertos,
                "total": total,
            },
            ts,
        )

    def red(
        self,
        enviados: int,
        reenviados: int,
        descartados_ttl: int,
        ts: float | None = None,
    ) -> None:
        self.registrar(
            {
                "kind": "network",
                "run_id": self.run_id,
                "ts": 0.0,
                "peer": self.peer,
                "enviados": enviados,
                "reenviados": reenviados,
                "descartados_ttl": descartados_ttl,
            },
            ts,
        )


def iterar_archivo(ruta: Path) -> Iterator[Metrica]:
    try:
        with ruta.open("r", encoding="utf-8") as archivo:
            for numero, linea in enumerate(archivo, start=1):
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    registro: object = json.loads(linea)
                except json.JSONDecodeError as error:
                    raise MetricaError(
                        f"linea {numero} no es JSON valido en {ruta}"
                    ) from error
                try:
                    yield _validar_registro(registro)
                except MetricaError as error:
                    raise MetricaError(
                        f"linea {numero} invalida en {ruta}: {error}"
                    ) from error
    except OSError as error:
        raise MetricaError(f"no se pudo leer {ruta}") from error


def leer_metricas(ruta: Path) -> Iterator[Metrica]:
    """Itera sobre un archivo JSONL o sobre todos los de un directorio."""
    if ruta.is_dir():
        for archivo in sorted(ruta.glob(f"*{EXTENSION_JSONL}")):
            yield from iterar_archivo(archivo)
        return
    yield from iterar_archivo(ruta)


def serie_topic(
    metricas: Iterable[Metrica],
    topic: str,
    channel: CanalMetrica,
    peer: str | None = None,
) -> list[tuple[float, str, float]]:
    """Devuelve (ts, peer, value) para un topic x canal, ordenado por ts.

    Ante muestras repetidas del mismo instante y peer, se conserva la mas
    reciente (la agregacion espera una observacion por peer y segundo).
    """
    por_instante = {
        (m["ts"], m["peer"]): m["value"]
        for m in metricas
        if m["kind"] == "topic"
        and m["topic"] == topic
        and m["channel"] == channel
        and (peer is None or m["peer"] == peer)
    }
    serie = [(ts, pid, valor) for (ts, pid), valor in por_instante.items()]
    serie.sort(key=lambda t: t[0])
    return serie


def brecha_percepcion(
    metricas: Iterable[Metrica],
    topic: str,
    peer: str | None = None,
) -> list[tuple[float, str, float]]:
    """Devuelve (ts, peer, subjetivo - objetivo) por último objetivo conocido.

    Ante rumores repetidos del mismo instante y peer se conserva el mas reciente;
    asi un peer aporta una sola brecha por segundo, sin duplicados por regrabado.
    """
    ultimo_objetivo: dict[str, float] = {}
    brechas: dict[tuple[float, str], float] = {}
    for m in sorted(metricas, key=lambda r: r["ts"]):
        if m["kind"] != "topic" or m["topic"] != topic:
            continue
        if peer is not None and m["peer"] != peer:
            continue
        if m["channel"] == "objetivo":
            ultimo_objetivo[m["peer"]] = m["value"]
        elif m["channel"] == "subjetivo" and m["peer"] in ultimo_objetivo:
            brechas[(m["ts"], m["peer"])] = m["value"] - ultimo_objetivo[m["peer"]]
    return sorted(
        ((ts, pid, gap) for (ts, pid), gap in brechas.items()),
        key=lambda triple: triple[0],
    )


@dataclass(frozen=True)
class ResumenConvergencia:
    serie: list[tuple[float, float, float, int]]
    convergido: bool
    ts_convergencia: float | None
    dispersion_final: float


def convergencia(
    metricas: Iterable[Metrica],
    topic: str,
    channel: CanalMetrica,
    eps: float,
    bucket: float = 0.1,
    peer: str | None = None,
) -> ResumenConvergencia:
    """Mide la alineación entre peers para un tópico y canal.

    Agrupa las muestras por ventana de ``bucket`` segundos y calcula el spread
    (max - min) y la desviación estándar de los valores entre peers. Se considera
    convergido cuando el spread es menor o igual a ``eps``.
    """
    if eps < 0:
        raise ValueError("eps no puede ser negativo")
    if bucket <= 0:
        raise ValueError("bucket debe ser positivo")

    por_bucket: dict[float, list[float]] = {}
    for m in metricas:
        if m["kind"] != "topic" or m["topic"] != topic or m["channel"] != channel:
            continue
        if peer is not None and m["peer"] != peer:
            continue
        ventana = math.floor(m["ts"] / bucket) * bucket
        por_bucket.setdefault(ventana, []).append(m["value"])

    serie: list[tuple[float, float, float, int]] = []
    convergido = False
    ts_convergencia: float | None = None
    dispersion_final = float("nan")

    for ventana in sorted(por_bucket):
        valores = por_bucket[ventana]
        minimo = min(valores)
        maximo = max(valores)
        spread = maximo - minimo
        desviacion = statistics.pstdev(valores) if len(valores) > 1 else 0.0
        serie.append((ventana, spread, desviacion, len(valores)))
        dispersion_final = spread
        if not convergido and spread <= eps:
            convergido = True
            ts_convergencia = ventana

    return ResumenConvergencia(
        serie=serie,
        convergido=convergido,
        ts_convergencia=ts_convergencia,
        dispersion_final=dispersion_final,
    )


def ultimo_valor(
    metricas: Iterable[Metrica],
    topic: str,
    channel: CanalMetrica,
) -> dict[str, float]:
    """Devuelve el último valor conocido por peer para un tópico y canal."""
    ultimo: dict[str, float] = {}
    for m in metricas:
        if m["kind"] != "topic" or m["topic"] != topic or m["channel"] != channel:
            continue
        ultimo[m["peer"]] = m["value"]
    return ultimo
