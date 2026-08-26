"""Scaffolding compartido por los publicadores de dominio (A y B).

Ambos publicadores necesitan lo mismo más allá de su ``step()``: escuchar sus
propios rumores (``Q``) en el canal subjetivo de su comuna, filtrando sus
propios mensajes, y avanzar un paso cada ``intervalo_segundos`` de tiempo real.
"""

import time
from collections.abc import Callable
from typing import Any

from civicmesh.comunas import normalizar_tópico
from civicmesh.domains.percepcion import AgregadorRumores, ResumenRumores
from civicmesh.protocol import PeerId
from civicmesh.pubsub import PubSub


class PublisherBase:
    """Wiring común: agregador de rumores propios y el scheduler de ``tick()``."""

    def __init__(
        self,
        comuna: str,
        pubsub: PubSub,
        peer_id: PeerId,
        resumen_rumores: ResumenRumores,
        dt: float,
        intervalo_segundos: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if dt <= 0:
            raise ValueError("dt debe ser positivo")
        if intervalo_segundos <= 0:
            raise ValueError("intervalo_segundos debe ser positivo")

        self._comuna = normalizar_tópico(comuna)
        self._pubsub = pubsub
        self._peer_id = peer_id
        self._rumores = AgregadorRumores(resumen_rumores)
        self._dt = dt
        self._intervalo = intervalo_segundos
        self._clock = clock

        self._t = 0.0
        self._next_send = 0.0

        pubsub.agregar_callback(self._on_mensaje)

    def _on_mensaje(self, mensaje: dict[str, Any]) -> None:
        if mensaje.get("channel") != "subjetivo":
            return
        if normalizar_tópico(str(mensaje.get("topic", ""))) != self._comuna:
            return
        if mensaje.get("origin") == self._peer_id:
            return

        contenido = mensaje.get("content")
        if not isinstance(contenido, dict):
            return
        valor = contenido.get("value")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            self._rumores.agregar(float(valor))

    def step(self, t: float) -> object:
        raise NotImplementedError

    def tick(self, now: float) -> None:
        """Compatible con ``civicmesh.node.Node``: avanza un paso por intervalo."""
        if now < self._next_send:
            return
        self._next_send = now + self._intervalo
        self.step(self._t)
        self._t += self._dt
