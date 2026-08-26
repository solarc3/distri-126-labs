import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from civicmesh.comunas import normalizar_tópico
from civicmesh.domains.coords import Coordenada


class SerieAireError(ValueError):
    """indica que un archivo cacheado no representa una serie de aire valida"""


@dataclass
class SerieAire:
    """serie horaria cacheada para una comuna/estacion con datos reales"""

    comuna: str
    fuente: str
    coordenadas: Coordenada
    tiempos: list[str]
    variables: dict[str, list[float]]

    def __len__(self) -> int:
        return len(self.tiempos)

    def tiene(self, variable: str) -> bool:
        return variable in self.variables

    def valor(self, indice: int, variable: str) -> float:
        serie = self.variables.get(variable)
        if serie is None:
            raise SerieAireError(f"{self.comuna} no tiene la variable {variable}")
        if not 0 <= indice < len(serie):
            raise SerieAireError(
                f"indice {indice} fuera de rango para {self.comuna} ({variable})"
            )
        return serie[indice]


def _rellenar_huecos(valores: list[object], ruta: str) -> list[float]:
    numericos: list[float | None] = []
    for indice, v in enumerate(valores):
        if v is None:
            numericos.append(None)
        elif isinstance(v, bool) or not isinstance(v, (int, float)):
            raise SerieAireError(f"{ruta}[{indice}] no es numerico ni nulo")
        else:
            numericos.append(float(v))

    conocidos = [v for v in numericos if v is not None]
    if not conocidos:
        raise SerieAireError(f"{ruta} no tiene ningun valor numerico")

    rellenados: list[float] = []
    ultimo = conocidos[0]
    for v in numericos:
        if v is not None:
            ultimo = v
        rellenados.append(ultimo)
    return rellenados


def cargar_serie(path: Path) -> SerieAire:
    try:
        contenido = path.read_text(encoding="utf-8")
        raw: object = json.loads(contenido)
    except OSError as error:
        raise SerieAireError(f"no se pudo leer {path}") from error
    except json.JSONDecodeError as error:
        raise SerieAireError(f"JSON invalido en {path}") from error

    if not isinstance(raw, dict):
        raise SerieAireError(f"{path} debe contener un objeto JSON")
    datos = cast(dict[str, object], raw)

    comuna_raw = datos.get("comuna")
    if not isinstance(comuna_raw, str) or not comuna_raw:
        raise SerieAireError(f"{path}: falta 'comuna'")
    comuna = normalizar_tópico(comuna_raw)

    fuente = datos.get("fuente")
    if not isinstance(fuente, str) or not fuente:
        raise SerieAireError(f"{path}: falta 'fuente'")

    latitude, longitude = datos.get("latitude"), datos.get("longitude")
    if isinstance(latitude, bool) or not isinstance(latitude, (int, float)):
        raise SerieAireError(f"{path}: 'latitude' debe ser numerico")
    if isinstance(longitude, bool) or not isinstance(longitude, (int, float)):
        raise SerieAireError(f"{path}: 'longitude' debe ser numerico")

    hourly = datos.get("hourly")
    if not isinstance(hourly, dict):
        raise SerieAireError(f"{path}: falta 'hourly'")
    hourly_map = cast(dict[str, object], hourly)

    tiempos_raw = hourly_map.get("time")
    if not isinstance(tiempos_raw, list) or not all(
        isinstance(t, str) and t for t in tiempos_raw
    ):
        raise SerieAireError(f"{path}: 'hourly.time' debe ser una lista de textos")
    tiempos = cast(list[str], tiempos_raw)
    if not tiempos:
        raise SerieAireError(f"{path}: la serie no puede estar vacia")

    variables: dict[str, list[float]] = {}
    for nombre, valores in hourly_map.items():
        if nombre == "time":
            continue
        if not isinstance(valores, list):
            raise SerieAireError(f"{path}: 'hourly.{nombre}' debe ser una lista")
        if len(valores) != len(tiempos):
            raise SerieAireError(
                f"{path}: 'hourly.{nombre}' debe tener {len(tiempos)} elementos"
            )
        variables[nombre] = _rellenar_huecos(
            cast(list[object], valores), f"{path}:hourly.{nombre}"
        )

    if not variables:
        raise SerieAireError(
            f"{path}: 'hourly' no tiene ninguna variable ademas de 'time'"
        )

    return SerieAire(
        comuna=comuna,
        fuente=fuente,
        coordenadas=(float(latitude), float(longitude)),
        tiempos=tiempos,
        variables=variables,
    )


def cargar_series_directorio(directorio: Path) -> dict[str, SerieAire]:
    """carga cada ``*.json`` de ``directorio``: las comunas con serie propia

    el conjunto resultante es ``S``
    """
    if not directorio.is_dir():
        raise SerieAireError(f"{directorio} no es un directorio")

    series: dict[str, SerieAire] = {}
    for path in sorted(directorio.glob("*.json")):
        serie = cargar_serie(path)
        if serie.comuna in series:
            raise SerieAireError(
                f"comuna duplicada entre archivos de cache: {serie.comuna}"
            )
        series[serie.comuna] = serie
    return series
