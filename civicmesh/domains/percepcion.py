import math
import random
from dataclasses import dataclass
from typing import Literal

ResumenRumores = Literal["promedio", "maximo"]


class PercepcionError(ValueError):
    """indica una configuracion o un valor invalido para el canal subjetivo"""


@dataclass
class MemoriaEMA:
    alpha: float
    valor: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0:
            raise PercepcionError("alpha debe estar en (0, 1)")

    def actualizar(self, estimulo: float) -> float:
        self.valor = self.alpha * self.valor + (1.0 - self.alpha) * estimulo
        return self.valor


class AgregadorRumores:
    def __init__(self, resumen: ResumenRumores = "promedio") -> None:
        if resumen not in ("promedio", "maximo"):
            raise PercepcionError(f"resumen de rumores desconocido: {resumen}")
        self._resumen = resumen
        self._valores: list[float] = []

    def agregar(self, valor: float) -> None:
        self._valores.append(valor)

    def resumen(self) -> float:
        if not self._valores:
            return 0.0
        if self._resumen == "maximo":
            return max(self._valores)
        return sum(self._valores) / len(self._valores)

    def vaciar(self) -> None:
        self._valores.clear()

    def __len__(self) -> int:
        return len(self._valores)


def sigmoide(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def clip(valor: float, minimo: float, maximo: float) -> float:
    if minimo > maximo:
        raise PercepcionError("minimo no puede ser mayor que maximo")
    return max(minimo, min(maximo, valor))


def ruido_gaussiano(rng: random.Random, sigma: float) -> float:
    if sigma < 0:
        raise PercepcionError("sigma no puede ser negativo")
    if sigma == 0:
        return 0.0
    return rng.gauss(0.0, sigma)
