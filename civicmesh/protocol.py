"""Define el formato comun de los mensajes intercambiados por CivicMesh."""

import json
import math
from typing import Literal, TypeAlias, TypedDict, cast

TipoMensaje: TypeAlias = Literal["gossip", "pubsub"]
PeerId: TypeAlias = str
JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

Sobre = TypedDict(
    "Sobre",
    {
        "tipo": TipoMensaje,
        "from": PeerId,
        "payload": dict[str, JsonValue],
    },
)


class ProtocolError(ValueError):
    """Indica que los datos no contienen un sobre valido."""


def _rechazar_constante_json(valor: str) -> object:
    raise ProtocolError(f"constante JSON no valida: {valor}")


def _leer_json(data: bytes) -> object:
    try:
        texto = data.decode("utf-8")
        datos: object = json.loads(
            texto,
            parse_constant=_rechazar_constante_json,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("el datagrama no contiene JSON valido") from error
    return datos


def _validar_json_value(
    valor: object,
    ruta: str,
    ancestros: set[int],
) -> None:
    if valor is None or isinstance(valor, (bool, int, str)):
        return

    if isinstance(valor, float):
        if not math.isfinite(valor):
            raise ProtocolError(f"{ruta} contiene un numero no finito")
        return

    if isinstance(valor, list):
        identidad = id(valor)
        if identidad in ancestros:
            raise ProtocolError(f"{ruta} contiene una referencia circular")
        ancestros.add(identidad)
        try:
            for indice, elemento in enumerate(valor):
                _validar_json_value(
                    elemento,
                    f"{ruta}[{indice}]",
                    ancestros,
                )
        finally:
            ancestros.remove(identidad)
        return

    if isinstance(valor, dict):
        identidad = id(valor)
        if identidad in ancestros:
            raise ProtocolError(f"{ruta} contiene una referencia circular")
        ancestros.add(identidad)
        try:
            for clave, elemento in valor.items():
                if not isinstance(clave, str):
                    raise ProtocolError(f"{ruta} contiene una clave no textual")
                _validar_json_value(
                    elemento,
                    f"{ruta}.{clave}",
                    ancestros,
                )
        finally:
            ancestros.remove(identidad)
        return

    raise ProtocolError(f"{ruta} contiene un valor no compatible con JSON")


def _validar_sobre(datos: object) -> Sobre:
    if not isinstance(datos, dict):
        raise ProtocolError("el JSON raiz debe ser un objeto")

    campos_requeridos = {"tipo", "from", "payload"}
    if not campos_requeridos.issubset(datos):
        raise ProtocolError("faltan campos obligatorios en el sobre")

    tipo = datos["tipo"]
    if tipo not in ("gossip", "pubsub"):
        raise ProtocolError("tipo de mensaje desconocido")

    remitente = datos["from"]
    if not isinstance(remitente, str) or not remitente:
        raise ProtocolError("from debe ser un peer ID no vacio")

    payload = datos["payload"]
    if not isinstance(payload, dict):
        raise ProtocolError("payload debe ser un objeto JSON")

    _validar_json_value(datos, "sobre", set())
    return cast(Sobre, datos)


def decodificar_sobre(data: bytes) -> Sobre:
    return _validar_sobre(_leer_json(data))


def codificar_sobre(sobre: Sobre) -> bytes:
    sobre_validado = _validar_sobre(sobre)
    try:
        texto = json.dumps(
            sobre_validado,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ProtocolError("el sobre no puede convertirse a JSON") from error

    return texto.encode("utf-8")
