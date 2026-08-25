import unittest
from pathlib import Path
from typing import Any, cast

from civicmesh.domains.air_quality_cache import cargar_series_directorio
from civicmesh.domains.config import PercepcionAireConfig
from civicmesh.domains.domain_b import DomainBPublisher
from civicmesh.domains.extrapolacion import ProveedorAire
from civicmesh.domains.replay import ReplayAgotadoError, ReplayAire
from civicmesh.membership.view import MembershipView
from civicmesh.protocol import Sobre
from civicmesh.pubsub import PoliticasCanales, PubSub
from civicmesh.transport import Transport

FIXTURES = Path(__file__).parent / "fixtures" / "air_quality"

POLITICAS_PUBSUB: PoliticasCanales = {
    "objetivo": {"ttl": 5, "priority": 2},
    "subjetivo": {"ttl": 3, "priority": 1},
}

PERCEPCION_AIRE: PercepcionAireConfig = {
    "alpha": 0.85,
    "gamma": 0.6,
    "delta": 0.3,
    "sigma_eps": 0.0,
    "clip_min": 0.0,
    "clip_max": 500.0,
    "resumen_rumores": "promedio",
}


class RecordingTransport:
    def __init__(self, peer_id: str) -> None:
        self.peer_id = peer_id
        self.sent: list[tuple[str, Sobre]] = []

    def send(self, peer_id: str, sobre: Sobre) -> None:
        self.sent.append((peer_id, sobre))


def _construir_pubsub(
    peer_id: str,
) -> tuple[PubSub, MembershipView, RecordingTransport]:
    vista = MembershipView(peer_id, [], t_suspect=10, t_dead=20)
    transporte = RecordingTransport(peer_id)
    pubsub = PubSub(vista, cast(Transport, transporte), POLITICAS_PUBSUB)
    return pubsub, vista, transporte


def _replay_santiago(loop: bool = True) -> ReplayAire:
    series = cargar_series_directorio(FIXTURES)
    proveedor = ProveedorAire(series, "idw")
    return ReplayAire("santiago", proveedor, loop=loop)


class DomainBPublisherTests(unittest.TestCase):
    def test_step_publica_la_muestra_real_en_objetivo_y_pc_en_subjetivo(self) -> None:
        pubsub, _vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        recibidos: list[dict[str, Any]] = []
        pubsub.agregar_callback(recibidos.append)

        publicador = DomainBPublisher(
            "santiago",
            _replay_santiago(),
            PERCEPCION_AIRE,
            pubsub,
            "127.0.0.1:7001",
            seed=126,
        )
        paso = publicador.step(0.0)

        objetivo = next(m for m in recibidos if m["channel"] == "objetivo")
        self.assertEqual(objetivo["content"]["pm2_5"], 80.0)
        self.assertEqual(objetivo["content"]["fuente"], "propia:open-meteo")

        subjetivo = next(m for m in recibidos if m["channel"] == "subjetivo")
        self.assertEqual(subjetivo["content"]["value"], paso.p_c)

    def test_primer_paso_sigue_la_formula_de_percepcion_sin_ruido_ni_rumor(
        self,
    ) -> None:
        pubsub, _vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        publicador = DomainBPublisher(
            "santiago",
            _replay_santiago(),
            PERCEPCION_AIRE,
            pubsub,
            "127.0.0.1:7001",
            seed=126,
        )
        paso = publicador.step(0.0)

        v_c = 80.0
        m_c_esperado = (
            PERCEPCION_AIRE["alpha"] * 0.0 + (1 - PERCEPCION_AIRE["alpha"]) * v_c
        )
        p_c_esperado = v_c + PERCEPCION_AIRE["gamma"] * (m_c_esperado - v_c)
        self.assertAlmostEqual(paso.m_c, m_c_esperado)
        self.assertAlmostEqual(paso.p_c, p_c_esperado)

    def test_memoria_de_pico_no_baja_tan_rapido_como_v_c(self) -> None:
        pubsub, _vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        publicador = DomainBPublisher(
            "santiago",
            _replay_santiago(),
            PERCEPCION_AIRE,
            pubsub,
            "127.0.0.1:7001",
            seed=126,
        )
        pasos = [publicador.step(float(t)) for t in range(4)]

        for paso in pasos:
            self.assertGreaterEqual(paso.u_c, paso.v_c)
        self.assertGreater(pasos[-1].p_c, pasos[-1].v_c)

    def test_clip_acota_p_c_al_rango_configurado(self) -> None:
        percepcion: PercepcionAireConfig = {**PERCEPCION_AIRE, "clip_max": 10.0}
        pubsub, _vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        publicador = DomainBPublisher(
            "santiago",
            _replay_santiago(),
            percepcion,
            pubsub,
            "127.0.0.1:7001",
            seed=126,
        )
        paso = publicador.step(0.0)
        self.assertLessEqual(paso.p_c, 10.0)

    def test_rumor_de_otro_peer_influye_en_el_siguiente_paso(self) -> None:
        pubsub, vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        publicador = DomainBPublisher(
            "santiago",
            _replay_santiago(),
            PERCEPCION_AIRE,
            pubsub,
            "127.0.0.1:7001",
            seed=126,
        )

        vista.contacto_directo("127.0.0.1:7002", 1, ["santiago"], 100.0)
        sobre: Sobre = {
            "tipo": "pubsub",
            "from": "127.0.0.1:7002",
            "payload": {
                "id": "rumor-1",
                "topic": "santiago",
                "channel": "subjetivo",
                "content": {"comuna": "santiago", "value": 300.0, "t": 0.0},
                "ttl": 2,
                "priority": 1,
                "origin": "127.0.0.1:7002",
            },
        }
        pubsub.handle(sobre)

        paso = publicador.step(0.0)
        self.assertAlmostEqual(paso.p_gossip, 300.0)

    def test_replay_agotado_sin_loop_propaga_el_error(self) -> None:
        pubsub, _vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        publicador = DomainBPublisher(
            "santiago",
            _replay_santiago(loop=False),
            PERCEPCION_AIRE,
            pubsub,
            "127.0.0.1:7001",
            seed=126,
        )
        for t in range(4):
            publicador.step(float(t))

        with self.assertRaises(ReplayAgotadoError):
            publicador.step(4.0)

    def test_tick_respeta_el_intervalo_configurado(self) -> None:
        pubsub, _vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        publicador = DomainBPublisher(
            "santiago",
            _replay_santiago(),
            PERCEPCION_AIRE,
            pubsub,
            "127.0.0.1:7001",
            seed=126,
            intervalo_segundos=1.0,
        )

        publicador.tick(0.0)
        self.assertEqual(len(publicador.historial), 1)
        publicador.tick(0.5)
        self.assertEqual(len(publicador.historial), 1)
        publicador.tick(1.0)
        self.assertEqual(len(publicador.historial), 2)


if __name__ == "__main__":
    unittest.main()
