from collections.abc import Callable, Mapping
from typing import Literal, TypedDict

from civicmesh.comunas import COMUNAS_ADYACENTES, normalizar_tópico
from civicmesh.domains.air_quality_cache import SerieAire, SerieAireError
from civicmesh.domains.coords import (
    CoordenadasError,
    coordenadas_de,
    distancia_haversine_km,
)

MetodoExtrapolacion = Literal["vecino_mas_cercano", "promedio_vecinos", "idw"]


class ExtrapolacionError(ValueError):
    """indica que no fue posible extrapolar ``v_c(t)`` para una comuna"""


class MuestraAire(TypedDict):
    comuna: str
    pm2_5: float | None
    pm10: float | None
    timestamp: str
    fuente: str


def vecino_mas_cercano(
    comuna: str,
    indice: int,
    series: Mapping[str, SerieAire],
    *,
    variable: str = "pm2_5",
) -> float:
    """``v_c(t) = v_{s*}(t)``, con ``s* = argmin_{s in S} d(c, s)``"""
    candidatos = [s for s in series.values() if s.tiene(variable)]
    if not candidatos:
        raise ExtrapolacionError(f"ninguna comuna de S tiene la variable {variable}")

    destino = coordenadas_de(comuna)
    mas_cercana = min(
        candidatos,
        key=lambda serie: distancia_haversine_km(destino, serie.coordenadas),
    )
    return mas_cercana.valor(indice, variable)


def promedio_vecinos(
    comuna: str,
    indice: int,
    series: Mapping[str, SerieAire],
    *,
    variable: str = "pm2_5",
) -> float:
    """``v_c(t) = promedio_{s in N(c)} v_s(t)``, sobre vecinas con serie propia"""
    vecinas = COMUNAS_ADYACENTES.get(normalizar_tópico(comuna), frozenset())
    disponibles = [
        series[vecina].valor(indice, variable)
        for vecina in vecinas
        if vecina in series and series[vecina].tiene(variable)
    ]
    if not disponibles:
        raise ExtrapolacionError(
            f"{comuna} no tiene comunas vecinas con la variable {variable} en S"
        )
    return sum(disponibles) / len(disponibles)


def idw(
    comuna: str,
    indice: int,
    series: Mapping[str, SerieAire],
    *,
    variable: str = "pm2_5",
    potencia: float = 2.0,
) -> float:
    """``v_c(t) = sum(w_s v_s(t)) / sum(w_s)``, ``w_s = 1/d(c,s)^p``"""
    candidatos = [s for s in series.values() if s.tiene(variable)]
    if not candidatos:
        raise ExtrapolacionError(f"ninguna comuna de S tiene la variable {variable}")

    destino = coordenadas_de(comuna)
    numerador = 0.0
    denominador = 0.0
    for serie in candidatos:
        distancia = distancia_haversine_km(destino, serie.coordenadas)
        if distancia == 0.0:
            return serie.valor(indice, variable)
        peso = 1.0 / (distancia**potencia)
        numerador += peso * serie.valor(indice, variable)
        denominador += peso

    return numerador / denominador


_METODOS: dict[str, Callable[..., float]] = {
    "vecino_mas_cercano": vecino_mas_cercano,
    "promedio_vecinos": promedio_vecinos,
    "idw": idw,
}


class ProveedorAire:
    """Da ``v_c(t)`` para cualquier comuna: propia si esta en ``S``, si no extrapola"""

    def __init__(
        self,
        series: dict[str, SerieAire],
        metodo: MetodoExtrapolacion,
        potencia: float = 2.0,
    ) -> None:
        if metodo not in _METODOS:
            raise ExtrapolacionError(f"metodo de extrapolacion desconocido: {metodo}")
        if not series:
            raise ExtrapolacionError("series (S) no puede estar vacio")
        self._series = series
        self._metodo = metodo
        self._potencia = potencia

    @property
    def comunas_con_serie_propia(self) -> frozenset[str]:
        return frozenset(self._series)

    def longitud(self) -> int:
        return min(len(serie) for serie in self._series.values())

    def muestra(self, comuna: str, indice: int) -> MuestraAire:
        normalizado = normalizar_tópico(comuna)
        propia = self._series.get(normalizado)
        if propia is not None:
            return {
                "comuna": normalizado,
                "pm2_5": propia.valor(indice, "pm2_5")
                if propia.tiene("pm2_5")
                else None,
                "pm10": propia.valor(indice, "pm10") if propia.tiene("pm10") else None,
                "timestamp": propia.tiempos[indice],
                "fuente": f"propia:{propia.fuente}",
            }

        funcion = _METODOS[self._metodo]
        kwargs = {"potencia": self._potencia} if self._metodo == "idw" else {}
        pm2_5 = self._extrapolar_o_none(funcion, normalizado, indice, "pm2_5", kwargs)
        pm10 = self._extrapolar_o_none(funcion, normalizado, indice, "pm10", kwargs)
        if pm2_5 is None and pm10 is None:
            raise ExtrapolacionError(
                f"no se pudo extrapolar nada para {comuna} en t={indice}"
            )

        return {
            "comuna": normalizado,
            "pm2_5": pm2_5,
            "pm10": pm10,
            "timestamp": self._tiempo_referencia(indice),
            "fuente": f"heredado:{self._metodo}",
        }

    def _extrapolar_o_none(
        self,
        funcion: Callable[..., float],
        comuna: str,
        indice: int,
        variable: str,
        kwargs: dict[str, float],
    ) -> float | None:
        try:
            return funcion(comuna, indice, self._series, variable=variable, **kwargs)
        except (ExtrapolacionError, CoordenadasError):
            return None

    def _tiempo_referencia(self, indice: int) -> str:
        primera = next(iter(self._series.values()))
        try:
            return primera.tiempos[indice]
        except IndexError as error:
            raise SerieAireError(f"indice {indice} fuera de rango") from error
