"""Dominio B — Calidad del aire: canal objetivo (replay real) y subjetivo (percepción).

El canal objetivo no se genera estocásticamente (Sección 4.3): cada paso avanza
el ``ReplayAire`` de la comuna (dato real cacheado, o extrapolado espacialmente
si la comuna no tiene estación propia) y publica esa muestra tal cual. El canal
subjetivo aplica la memoria de pico y el arrastre por rumor de la Sección 4.2.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from civicmesh.comunas import normalizar_tópico
from civicmesh.domains.config import PercepcionAireConfig
from civicmesh.domains.extrapolacion import MuestraAire
from civicmesh.domains.mensajes import PercepcionPublicada
from civicmesh.domains.percepcion import MemoriaEMA, clip, ruido_gaussiano
from civicmesh.domains.publisher_base import PublisherBase
from civicmesh.domains.replay import ReplayAire
from civicmesh.domains.rng import rng_compuesto
from civicmesh.metrics import EscribirMetricas
from civicmesh.protocol import JsonValue, PeerId
from civicmesh.pubsub import PubSub

DOMINIO = "aire"


@dataclass
class PasoAire:
    """Resultado íntegro de un paso, útil para tests, métricas y el informe."""

    t: float
    v_c: float
    u_c: float
    m_c: float
    p_gossip: float
    p_c: float
    muestra: MuestraAire


class DomainBPublisher(PublisherBase):
    """Publicador de Dominio B para una comuna: replay real + percepción simulada."""

    def __init__(
        self,
        comuna: str,
        replay: ReplayAire,
        percepcion: PercepcionAireConfig,
        pubsub: PubSub,
        peer_id: PeerId,
        seed: int,
        dt: float = 1.0,
        intervalo_segundos: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        metricas: EscribirMetricas | None = None,
    ) -> None:
        if replay.comuna != normalizar_tópico(comuna):
            raise ValueError("el replay entregado pertenece a otra comuna")

        super().__init__(
            comuna=comuna,
            pubsub=pubsub,
            peer_id=peer_id,
            resumen_rumores=percepcion["resumen_rumores"],
            dt=dt,
            intervalo_segundos=intervalo_segundos,
            clock=clock,
        )

        self._replay = replay
        self._percepcion_cfg = percepcion
        self._metricas = metricas
        self._rng_ruido = rng_compuesto(seed, "aire", self._comuna, "eps")
        self._memoria = MemoriaEMA(percepcion["alpha"])
        self.historial: list[PasoAire] = []

    def step(self, t: float) -> PasoAire:
        """Ejecuta un paso completo (Sección 4.2/4.3) y devuelve sus valores."""
        muestra = self._replay.step()
        v_c = muestra["pm2_5"]
        if v_c is None:
            raise ValueError(
                f"sin pm2_5 (propio/extrapolado) para {self._comuna} en t={t}"
            )

        self._pubsub.publish(
            self._comuna,
            cast(JsonValue, dict(muestra)),
            channel="objetivo",
        )

        cfg = self._percepcion_cfg
        u_c = max(v_c, self._memoria.valor)
        m_c = self._memoria.actualizar(u_c)
        p_gossip = self._rumores.resumen()
        self._rumores.vaciar()
        eps = ruido_gaussiano(self._rng_ruido, cfg["sigma_eps"])
        p_c = clip(
            v_c + cfg["gamma"] * (m_c - v_c) + cfg["delta"] * p_gossip + eps,
            cfg["clip_min"],
            cfg["clip_max"],
        )

        subjetivo: PercepcionPublicada = {"comuna": self._comuna, "value": p_c, "t": t}
        self._pubsub.publish(
            self._comuna,
            cast(JsonValue, dict(subjetivo)),
            channel="subjetivo",
        )

        if self._metricas is not None:
            self._metricas.topic(DOMINIO, self._comuna, "objetivo", v_c)
            self._metricas.topic(DOMINIO, self._comuna, "subjetivo", p_c)

        paso = PasoAire(
            t=t,
            v_c=v_c,
            u_c=u_c,
            m_c=m_c,
            p_gossip=p_gossip,
            p_c=p_c,
            muestra=muestra,
        )
        self.historial.append(paso)
        return paso
