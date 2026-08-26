"""Dominio A — Delitos: canal objetivo (Poisson) y subjetivo (inseguridad).

Implementa el flujo de "Quién genera qué" de la Sección 4.3 para un
publicador asociado a una única comuna:

1. Genera ``X_{c,k}(t) ~ Poisson(lambda_{c,k} * dt)`` por tipo de delito.
2. Publica cada evento en el canal objetivo.
3. Actualiza ``M_c`` (EMA) y calcula ``P_c(t)`` con el rumor ``\\hat P^gossip_c``
   acumulado desde el paso anterior.
4. Publica ``P_c(t)`` en el canal subjetivo del mismo tópico.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypedDict, cast

from civicmesh.domains.config import PercepcionDelitosConfig
from civicmesh.domains.mensajes import PercepcionPublicada
from civicmesh.domains.percepcion import MemoriaEMA, clip, ruido_gaussiano, sigmoide
from civicmesh.domains.publisher_base import PublisherBase
from civicmesh.domains.rng import poisson, rng_compuesto
from civicmesh.metrics import EscribirMetricas
from civicmesh.protocol import JsonValue, PeerId
from civicmesh.pubsub import PubSub

DOMINIO = "delitos"


class EventoDelito(TypedDict):
    """Evento discreto ``(comuna, tipo, count, t)`` del canal objetivo."""

    comuna: str
    tipo: str
    count: int
    t: float


@dataclass
class PasoDelitos:
    """Resultado íntegro de un paso, útil para tests, métricas y el informe."""

    t: float
    r_c: int
    m_c: float
    p_gossip: float
    z_c: float
    p_c: float
    eventos: list[EventoDelito] = field(default_factory=list)


class DomainAPublisher(PublisherBase):
    """Publicador de Dominio A para una comuna: genera y publica ambos canales."""

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

        super().__init__(
            comuna=comuna,
            pubsub=pubsub,
            peer_id=peer_id,
            resumen_rumores=percepcion["resumen_rumores"],
            dt=dt,
            intervalo_segundos=intervalo_segundos,
            clock=clock,
        )

        self._tasas = dict(tasas)
        self._percepcion_cfg = percepcion
        self._metricas = metricas
        self._rng_por_tipo = {
            tipo: rng_compuesto(seed, self._comuna, tipo) for tipo in self._tasas
        }
        self._rng_ruido = rng_compuesto(seed, self._comuna, "eps")
        self._memoria = MemoriaEMA(percepcion["alpha"])
        self.historial: list[PasoDelitos] = []

    def step(self, t: float) -> PasoDelitos:
        """Ejecuta un paso completo (Sección 4.3) y devuelve sus valores."""
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
