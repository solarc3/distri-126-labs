import math

from civicmesh.comunas import COMUNAS_ADYACENTES, normalizar_tópico

Coordenada = tuple[float, float]


class CoordenadasError(ValueError):
    """indica que una comuna no tiene coordenadas registradas"""


COORDENADAS_COMUNAS: dict[str, Coordenada] = {
    "santiago": (-33.4489, -70.6693),
    "providencia": (-33.4260, -70.6100),
    "las_condes": (-33.4089, -70.5183),
    "vitacura": (-33.3809, -70.5979),
    "nunoa": (-33.4558, -70.5990),
    "recoleta": (-33.4058, -70.6390),
    "independencia": (-33.4200, -70.6650),
    "quinta_normal": (-33.4270, -70.7020),
    "estacion_central": (-33.4590, -70.6790),
    "san_miguel": (-33.4960, -70.6500),
    "macul": (-33.4880, -70.5980),
    "la_reina": (-33.4450, -70.5390),
    "pedro_aguirre_cerda": (-33.4930, -70.6800),
    "lo_barnechea": (-33.3520, -70.5110),
    "huechuraba": (-33.3650, -70.6330),
    "san_joaquin": (-33.4930, -70.6280),
    "conchali": (-33.3800, -70.6750),
    "pudahuel": (-33.4420, -70.7580),
    "renca": (-33.4030, -70.7220),
    "maipu": (-33.5110, -70.7570),
    "cerrillos": (-33.4970, -70.7160),
    "la_cisterna": (-33.5330, -70.6620),
    "san_ramon": (-33.5390, -70.6420),
    "penalolen": (-33.4830, -70.5390),
    "la_florida": (-33.5230, -70.5910),
}


def _validar_cobertura() -> None:
    faltantes = COMUNAS_ADYACENTES.keys() - COORDENADAS_COMUNAS.keys()
    if faltantes:
        raise CoordenadasError(
            f"faltan coordenadas para comunas del grafo: {sorted(faltantes)}"
        )
    sobrantes = COORDENADAS_COMUNAS.keys() - COMUNAS_ADYACENTES.keys()
    if sobrantes:
        raise CoordenadasError(
            f"hay coordenadas de comunas fuera del grafo: {sorted(sobrantes)}"
        )


_validar_cobertura()


def coordenadas_de(comuna: str) -> Coordenada:
    normalizado = normalizar_tópico(comuna)
    try:
        return COORDENADAS_COMUNAS[normalizado]
    except KeyError as error:
        raise CoordenadasError(f"sin coordenadas para la comuna {comuna}") from error


def distancia_haversine_km(origen: Coordenada, destino: Coordenada) -> float:
    """distancia geografica ``d(c, s)`` en kilometros"""
    radio_tierra_km = 6371.0
    lat1, lon1 = math.radians(origen[0]), math.radians(origen[1])
    lat2, lon2 = math.radians(destino[0]), math.radians(destino[1])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * radio_tierra_km * math.asin(math.sqrt(a))
