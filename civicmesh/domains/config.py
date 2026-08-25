from pathlib import Path
from typing import TypedDict, cast

import yaml

from civicmesh.domains.extrapolacion import MetodoExtrapolacion
from civicmesh.domains.percepcion import ResumenRumores

RESUMENES_VALIDOS: tuple[ResumenRumores, ...] = ("promedio", "maximo")
METODOS_EXTRAPOLACION: tuple[MetodoExtrapolacion, ...] = (
    "vecino_mas_cercano",
    "promedio_vecinos",
    "idw",
)


class GeneradoresConfigError(ValueError):
    """indica que generadores.yaml no cumple lo esperado"""


class PercepcionDelitosConfig(TypedDict):
    alpha: float
    beta0: float
    beta1: float
    beta2: float
    sigma_eps: float
    resumen_rumores: ResumenRumores
    usar_sigmoide: bool


class DominioDelitosConfig(TypedDict):
    tasas: dict[str, dict[str, float]]
    percepcion: PercepcionDelitosConfig


class PercepcionAireConfig(TypedDict):
    alpha: float
    gamma: float
    delta: float
    sigma_eps: float
    clip_min: float
    clip_max: float
    resumen_rumores: ResumenRumores


class ExtrapolacionConfig(TypedDict):
    metodo: MetodoExtrapolacion
    potencia: float


class DominioAireConfig(TypedDict):
    comunas: list[str]
    percepcion: PercepcionAireConfig
    extrapolacion: ExtrapolacionConfig


class GeneradoresConfig(TypedDict):
    seed: int
    delitos: DominioDelitosConfig
    aire: DominioAireConfig


def _mapping(valor: object, ruta: str) -> dict[str, object]:
    if not isinstance(valor, dict):
        raise GeneradoresConfigError(f"{ruta} debe ser un objeto")
    if not all(isinstance(clave, str) for clave in valor):
        raise GeneradoresConfigError(f"{ruta} solo puede tener claves de texto")
    return cast(dict[str, object], valor)


def _number(valor: object, ruta: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise GeneradoresConfigError(f"{ruta} debe ser un numero")
    return float(valor)


def _integer(valor: object, ruta: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise GeneradoresConfigError(f"{ruta} debe ser un entero")
    return valor


def _bool(valor: object, ruta: str) -> bool:
    if not isinstance(valor, bool):
        raise GeneradoresConfigError(f"{ruta} debe ser booleano")
    return valor


def _alpha(valor: object, ruta: str) -> float:
    numero = _number(valor, ruta)
    if not 0.0 < numero < 1.0:
        raise GeneradoresConfigError(f"{ruta} debe estar en (0, 1)")
    return numero


def _no_negativo(valor: object, ruta: str) -> float:
    numero = _number(valor, ruta)
    if numero < 0:
        raise GeneradoresConfigError(f"{ruta} no puede ser negativo")
    return numero


def _resumen_rumores(valor: object, ruta: str) -> ResumenRumores:
    if valor not in RESUMENES_VALIDOS:
        raise GeneradoresConfigError(f"{ruta} debe ser uno de {RESUMENES_VALIDOS}")
    return cast(ResumenRumores, valor)


def _parse_tasas(valor: object, ruta: str) -> dict[str, dict[str, float]]:
    comunas = _mapping(valor, ruta)
    tasas: dict[str, dict[str, float]] = {}
    for comuna, tipos_raw in comunas.items():
        tipos = _mapping(tipos_raw, f"{ruta}.{comuna}")
        if not tipos:
            raise GeneradoresConfigError(f"{ruta}.{comuna} no puede estar vacio")
        tasas[comuna] = {
            tipo: _no_negativo(lam, f"{ruta}.{comuna}.{tipo}")
            for tipo, lam in tipos.items()
        }
    if not tasas:
        raise GeneradoresConfigError(f"{ruta} no puede estar vacio")
    return tasas


def _parse_percepcion_delitos(valor: object, ruta: str) -> PercepcionDelitosConfig:
    p = _mapping(valor, ruta)
    return {
        "alpha": _alpha(p.get("alpha"), f"{ruta}.alpha"),
        "beta0": _number(p.get("beta0"), f"{ruta}.beta0"),
        "beta1": _number(p.get("beta1"), f"{ruta}.beta1"),
        "beta2": _number(p.get("beta2"), f"{ruta}.beta2"),
        "sigma_eps": _no_negativo(p.get("sigma_eps"), f"{ruta}.sigma_eps"),
        "resumen_rumores": _resumen_rumores(
            p.get("resumen_rumores"), f"{ruta}.resumen_rumores"
        ),
        "usar_sigmoide": _bool(p.get("usar_sigmoide"), f"{ruta}.usar_sigmoide"),
    }


def _parse_percepcion_aire(valor: object, ruta: str) -> PercepcionAireConfig:
    p = _mapping(valor, ruta)
    clip_min = _number(p.get("clip_min"), f"{ruta}.clip_min")
    clip_max = _number(p.get("clip_max"), f"{ruta}.clip_max")
    if clip_min > clip_max:
        raise GeneradoresConfigError(f"{ruta}.clip_min no puede ser mayor a clip_max")
    return {
        "alpha": _alpha(p.get("alpha"), f"{ruta}.alpha"),
        "gamma": _number(p.get("gamma"), f"{ruta}.gamma"),
        "delta": _number(p.get("delta"), f"{ruta}.delta"),
        "sigma_eps": _no_negativo(p.get("sigma_eps"), f"{ruta}.sigma_eps"),
        "clip_min": clip_min,
        "clip_max": clip_max,
        "resumen_rumores": _resumen_rumores(
            p.get("resumen_rumores"), f"{ruta}.resumen_rumores"
        ),
    }


def _parse_extrapolacion(valor: object, ruta: str) -> ExtrapolacionConfig:
    e = _mapping(valor, ruta)
    metodo = e.get("metodo")
    if metodo not in METODOS_EXTRAPOLACION:
        raise GeneradoresConfigError(
            f"{ruta}.metodo debe ser uno de {METODOS_EXTRAPOLACION}"
        )
    potencia = _number(e.get("potencia", 2.0), f"{ruta}.potencia")
    if potencia < 1.0:
        raise GeneradoresConfigError(f"{ruta}.potencia debe ser >= 1")
    return {"metodo": cast(MetodoExtrapolacion, metodo), "potencia": potencia}


def _parse_comunas(valor: object, ruta: str) -> list[str]:
    if not isinstance(valor, list) or not all(isinstance(c, str) and c for c in valor):
        raise GeneradoresConfigError(f"{ruta} debe ser una lista de textos no vacios")
    if not valor:
        raise GeneradoresConfigError(f"{ruta} no puede estar vacio")
    return cast(list[str], valor)


def load_generadores_config(path: Path) -> GeneradoresConfig:
    try:
        contenido = path.read_text(encoding="utf-8")
        raw: object = yaml.safe_load(contenido)
    except OSError as error:
        raise GeneradoresConfigError(f"no se pudo leer {path}") from error
    except yaml.YAMLError as error:
        raise GeneradoresConfigError(f"YAML invalido en {path}") from error

    root = _mapping(raw, "config")
    seed = _integer(root.get("seed"), "seed")

    delitos_raw = _mapping(root.get("delitos"), "delitos")
    delitos: DominioDelitosConfig = {
        "tasas": _parse_tasas(delitos_raw.get("tasas"), "delitos.tasas"),
        "percepcion": _parse_percepcion_delitos(
            delitos_raw.get("percepcion"), "delitos.percepcion"
        ),
    }

    aire_raw = _mapping(root.get("aire"), "aire")
    aire: DominioAireConfig = {
        "comunas": _parse_comunas(aire_raw.get("comunas"), "aire.comunas"),
        "percepcion": _parse_percepcion_aire(
            aire_raw.get("percepcion"), "aire.percepcion"
        ),
        "extrapolacion": _parse_extrapolacion(
            aire_raw.get("extrapolacion"), "aire.extrapolacion"
        ),
    }

    return {"seed": seed, "delitos": delitos, "aire": aire}
