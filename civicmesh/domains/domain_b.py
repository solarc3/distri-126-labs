import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from civicmesh.comunas import normalizar_tópico
from civicmesh.domains.config import PercepcionAireConfig
from civicmesh.domains.extrapolacion import MuestraAire
from civicmesh.domains.mensajes import PercepcionPublicada
from civicmesh.domains.percepcion import (
    AgregadorRumores,
    MemoriaEMA,
    clip,
    ruido_gaussiano,
)
from civicmesh.domains.replay import ReplayAire
from civicmesh.domains.rng import rng_compuesto
from civicmesh.metrics import EscribirMetricas
from civicmesh.protocol import JsonValue, PeerId
from civicmesh.pubsub import PubSub

DOMINIO = "aire"


@dataclass
class PasoAire:
    t: float
    v_c: float
    u_c: float
    m_c: float
    p_gossip: float
    p_c: float
    muestra: MuestraAire


class DomainBPublisher:
    def __init__(
        self,
        comuna: str,
        replay: ReplayAire,
        percepcion: PercepcionAireConfig,
        pubsub: PubSub,
        peer_id: PeerId,
        seed: int,
        intervalo_segundos: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        metricas: EscribirMetricas | None = None,
    ) -> None:
        if intervalo_segundos <= 0:
            raise ValueError("intervalo_segundos debe ser positivo")
        if replay.comuna != normalizar_tópico(comuna):
            raise ValueError("el replay entregado pertenece a otra comuna")

        self._comuna = normalizar_tópico(comuna)
        self._replay = replay
        self._percepcion_cfg = percepcion
        self._pubsub = pubsub
        self._peer_id = peer_id
        self._intervalo = intervalo_segundos
        self._clock = clock
        self._metricas = metricas

        self._rng_ruido = rng_compuesto(seed, "aire", self._comuna, "eps")
        self._memoria = MemoriaEMA(percepcion["alpha"])
        self._rumores = AgregadorRumores(percepcion["resumen_rumores"])

        self._t = 0.0
        self._next_send = 0.0
        self.historial: list[PasoAire] = []

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

    def step(self, t: float) -> PasoAire:
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

    def tick(self, now: float) -> None:
        if now < self._next_send:
            return
        self._next_send = now + self._intervalo
        self.step(self._t)
        self._t += 1.0
