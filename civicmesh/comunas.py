"""Carga y consulta el grafo versionado de comunas."""

from pathlib import Path
from typing import cast

import yaml

GRAFO_COMUNAS_PATH = Path(__file__).with_name("comunas_rm.yaml")


class GrafoComunasError(ValueError):
    """Indica que el archivo de comunas no representa un grafo válido."""


def normalizar_tópico(tópico: str) -> str:
    """Normaliza un tópico/comuna a minúsculas y sin espacios adicionales."""
    return tópico.strip().lower()


def cargar_grafo_comunas(
    path: Path = GRAFO_COMUNAS_PATH,
) -> dict[str, frozenset[str]]:
    """Carga un grafo cerrado y simétrico desde un archivo YAML."""
    try:
        contenido = path.read_text(encoding="utf-8")
        raw: object = yaml.safe_load(contenido)
    except OSError as error:
        raise GrafoComunasError(f"no se pudo leer el grafo {path}") from error
    except yaml.YAMLError as error:
        raise GrafoComunasError(f"YAML inválido en el grafo {path}") from error

    if not isinstance(raw, dict):
        raise GrafoComunasError("el grafo debe ser un objeto")

    grafo: dict[str, frozenset[str]] = {}
    for comuna_raw, vecinos_raw in cast(dict[object, object], raw).items():
        if not isinstance(comuna_raw, str) or not comuna_raw:
            raise GrafoComunasError("cada comuna debe ser un texto no vacío")
        if comuna_raw != normalizar_tópico(comuna_raw):
            raise GrafoComunasError(f"comuna no normalizada: {comuna_raw}")
        if not isinstance(vecinos_raw, list) or not all(
            isinstance(vecino, str) and vecino
            for vecino in vecinos_raw
        ):
            raise GrafoComunasError(
                f"los vecinos de {comuna_raw} deben ser una lista de textos"
            )
        vecinos = cast(list[str], vecinos_raw)
        if any(vecino != normalizar_tópico(vecino) for vecino in vecinos):
            raise GrafoComunasError(f"vecino no normalizado para {comuna_raw}")
        if len(vecinos) != len(set(vecinos)):
            raise GrafoComunasError(f"hay vecinos duplicados para {comuna_raw}")
        if comuna_raw in vecinos:
            raise GrafoComunasError(f"{comuna_raw} no puede ser vecina de sí misma")

        grafo[comuna_raw] = frozenset(vecinos)

    for comuna, vecinos in grafo.items():
        for vecino in vecinos:
            if vecino not in grafo:
                raise GrafoComunasError(f"falta una entrada para {vecino}")
            if comuna not in grafo[vecino]:
                raise GrafoComunasError(
                    f"arista asimétrica entre {comuna} y {vecino}"
                )

    return grafo


COMUNAS_ADYACENTES = cargar_grafo_comunas()


def obtener_comunas_interes(tópico: str) -> set[str]:
    """Devuelve el tópico normalizado y sus comunas adyacentes."""
    normalizado = normalizar_tópico(tópico)
    return {normalizado, *COMUNAS_ADYACENTES.get(normalizado, ())}
