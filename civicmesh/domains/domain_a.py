import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypedDict, cast

from civicmesh.comunas import normalizar_tópico
from civicmesh.domains.config import PercepcionDelitosConfig
from civicmesh.domains.mensajes import PercepcionPublicada
from civicmesh.domains.percepcion import (
    AgregadorRumores,
    MemoriaEMA,
    clip,
    ruido_gaussiano,
    sigmoide,
)
from civicmesh.domains.rng import poisson, rng_compuesto
from civicmesh.metrics import EscribirMetricas
from civicmesh.protocol import JsonValue, PeerId
from civicmesh.pubsub import PubSub

DOMINIO = "delitos"


class EventoDelito(TypedDict):
    comuna: str
    tipo: str
    count: int
    t: float


@dataclass
class PasoDelitos:
    t: float
    r_c: int
    m_c: float
    p_gossip: float
    z_c: float
    p_c: float
    eventos: list[EventoDelito] = field(default_factory=list)


class DomainAPublisher:
    def __init__(
        self,
        comuna: str,
        tasas: dict[str, float],
        percepcion: PercepcionDelitosConfig,
        pubsub: PubSub,
        peer_id: PeerId,
        seed: int,
        dt: float = 1.0,
        intervalo_segundos: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        metricas: EscribirMetricas | None = None,
    ) -> None:
        if not tasas:
            raise ValueError("tasas no puede estar vacio")
        if dt <= 0:
            raise ValueError("dt debe ser positivo")
        if intervalo_segundos <= 0:
            raise ValueError("intervalo_segundos debe ser positivo")

        self._comuna = normalizar_tópico(comuna)
        self._tasas = dict(tasas)
        self._percepcion_cfg = percepcion
        self._pubsub = pubsub
        self._peer_id = peer_id
        self._dt = dt
        self._intervalo = intervalo_segundos
        self._clock = clock
        self._metricas = metricas

        self._rng_por_tipo = {
            tipo: rng_compuesto(seed, self._comuna, tipo) for tipo in self._tasas
        }
        self._rng_ruido = rng_compuesto(seed, self._comuna, "eps")
        self._memoria = MemoriaEMA(percepcion["alpha"])
        self._rumores = AgregadorRumores(percepcion["resumen_rumores"])

        self._t = 0.0
        self._next_send = 0.0
        self.historial: list[PasoDelitos] = []

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

    def step(self, t: float) -> PasoDelitos:
        eventos: list[EventoDelito] = []
        total = 0
        for tipo, lam in self._tasas.items():
            conteo = poisson(self._rng_por_tipo[tipo], lam * self._dt)
            total += conteo
            evento: EventoDelito = {
                "comuna": self._comuna,
                "tipo": tipo,
                "count": conteo,
                "t": t,
            }
            eventos.append(evento)
            self._pubsub.publish(
                self._comuna,
                cast(JsonValue, dict(evento)),
                channel="objetivo",
            )

        cfg = self._percepcion_cfg
        m_c = self._memoria.actualizar(float(total))
        p_gossip = self._rumores.resumen()
        self._rumores.vaciar()
        eps = ruido_gaussiano(self._rng_ruido, cfg["sigma_eps"])
        z_c = cfg["beta0"] + cfg["beta1"] * m_c + cfg["beta2"] * p_gossip + eps
        p_c = sigmoide(z_c) if cfg["usar_sigmoide"] else clip(z_c, 0.0, 1.0)

        subjetivo: PercepcionPublicada = {"comuna": self._comuna, "value": p_c, "t": t}
        self._pubsub.publish(
            self._comuna,
            cast(JsonValue, dict(subjetivo)),
            channel="subjetivo",
        )

        if self._metricas is not None:
            self._metricas.topic(DOMINIO, self._comuna, "objetivo", float(total))
            self._metricas.topic(DOMINIO, self._comuna, "subjetivo", p_c)

        paso = PasoDelitos(
            t=t,
            r_c=total,
            m_c=m_c,
            p_gossip=p_gossip,
            z_c=z_c,
            p_c=p_c,
            eventos=eventos,
        )
        self.historial.append(paso)
        return paso

    def tick(self, now: float) -> None:
        if now < self._next_send:
            return
        self._next_send = now + self._intervalo
        self.step(self._t)
        self._t += self._dt
