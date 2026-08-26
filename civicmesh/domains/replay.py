"""Replay determinista de una serie/extrapolación de aire para una comuna."""

from civicmesh.comunas import normalizar_tópico
from civicmesh.domains.extrapolacion import MuestraAire, ProveedorAire


class ReplayAgotadoError(StopIteration):
    """indica que la serie cacheada se agoto"""


class ReplayAire:
    def __init__(
        self, comuna: str, proveedor: ProveedorAire, loop: bool = True
    ) -> None:
        self._comuna = normalizar_tópico(comuna)
        self._proveedor = proveedor
        self._loop = loop
        self._indice = 0

    @property
    def comuna(self) -> str:
        return self._comuna

    def step(self) -> MuestraAire:
        longitud = self._proveedor.longitud()
        if self._indice >= longitud:
            if not self._loop:
                raise ReplayAgotadoError(
                    f"serie agotada para {self._comuna} (longitud={longitud})"
                )
            self._indice = 0

        muestra = self._proveedor.muestra(self._comuna, self._indice)
        self._indice += 1
        return muestra
