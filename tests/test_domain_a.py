import random
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

import yaml

from civicmesh.domains.config import (
    GeneradoresConfigError,
    PercepcionDelitosConfig,
    load_generadores_config,
)
from civicmesh.domains.domain_a import DomainAPublisher
from civicmesh.domains.rng import poisson, rng_compuesto
from civicmesh.membership.view import MembershipView
from civicmesh.protocol import Sobre
from civicmesh.pubsub import PoliticasCanales, PubSub
from civicmesh.transport import Transport

GENERADORES_PATH = Path(__file__).parents[1] / "generadores.example.yaml"

POLITICAS_PUBSUB: PoliticasCanales = {
    "objetivo": {"ttl": 5, "priority": 2},
    "subjetivo": {"ttl": 3, "priority": 1},
}

PERCEPCION_DELITOS: PercepcionDelitosConfig = {
    "alpha": 0.8,
    "beta0": -1.0,
    "beta1": 0.4,
    "beta2": 0.8,
    "sigma_eps": 0.1,
    "resumen_rumores": "promedio",
    "usar_sigmoide": True,
}


class RecordingTransport:
    def __init__(self, peer_id: str) -> None:
        self.peer_id = peer_id
        self.sent: list[tuple[str, Sobre]] = []

    def send(self, peer_id: str, sobre: Sobre) -> None:
        self.sent.append((peer_id, sobre))


class RngTests(unittest.TestCase):
    def test_rng_compuesto_es_reproducible(self) -> None:
        rng_a = rng_compuesto(126, "santiago", "robo")
        rng_b = rng_compuesto(126, "santiago", "robo")
        self.assertEqual(
            [poisson(rng_a, 0.5) for _ in range(20)],
            [poisson(rng_b, 0.5) for _ in range(20)],
        )

    def test_rng_compuesto_distingue_comuna_y_tipo(self) -> None:
        rng_santiago = rng_compuesto(126, "santiago", "robo")
        rng_providencia = rng_compuesto(126, "providencia", "robo")
        secuencia_1 = [poisson(rng_santiago, 0.5) for _ in range(50)]
        secuencia_2 = [poisson(rng_providencia, 0.5) for _ in range(50)]
        self.assertNotEqual(secuencia_1, secuencia_2)

    def test_poisson_lambda_cero_siempre_da_cero(self) -> None:
        rng = random.Random(1)
        self.assertEqual([poisson(rng, 0.0) for _ in range(10)], [0] * 10)

    def test_poisson_lambda_negativo_falla(self) -> None:
        with self.assertRaises(ValueError):
            poisson(random.Random(1), -1.0)

    def test_poisson_promedio_se_acerca_a_lambda(self) -> None:
        rng = random.Random(7)
        lam = 3.0
        muestras = [poisson(rng, lam) for _ in range(20_000)]
        promedio = sum(muestras) / len(muestras)
        self.assertAlmostEqual(promedio, lam, delta=0.1)


class GeneradoresConfigTests(unittest.TestCase):
    def test_carga_el_archivo_de_ejemplo_del_repositorio(self) -> None:
        config = load_generadores_config(GENERADORES_PATH)

        self.assertEqual(config["seed"], 126)
        self.assertIn("santiago", config["delitos"]["tasas"])
        self.assertIn("robo", config["delitos"]["tasas"]["santiago"])
        self.assertEqual(config["delitos"]["percepcion"]["alpha"], 0.8)
        self.assertIn("aire", config)
        self.assertIn("santiago", config["aire"]["comunas"])
        self.assertEqual(config["aire"]["extrapolacion"]["metodo"], "idw")

    def _cargar_con_override(self, mutador: Any) -> None:
        contenido = yaml.safe_load(GENERADORES_PATH.read_text(encoding="utf-8"))
        mutador(contenido)
        with tempfile.TemporaryDirectory() as directorio:
            path = Path(directorio) / "generadores.yaml"
            path.write_text(yaml.safe_dump(contenido), encoding="utf-8")
            with self.assertRaises(GeneradoresConfigError):
                load_generadores_config(path)

    def test_alpha_fuera_de_rango_falla(self) -> None:
        self._cargar_con_override(
            lambda c: c["delitos"]["percepcion"].__setitem__("alpha", 1.5)
        )

    def test_tasa_negativa_falla(self) -> None:
        self._cargar_con_override(
            lambda c: c["delitos"]["tasas"]["santiago"].__setitem__("robo", -0.1)
        )

    def test_metodo_de_extrapolacion_desconocido_falla(self) -> None:
        self._cargar_con_override(
            lambda c: c["aire"]["extrapolacion"].__setitem__("metodo", "otro")
        )

    def test_resumen_de_rumores_desconocido_falla(self) -> None:
        self._cargar_con_override(
            lambda c: c["delitos"]["percepcion"].__setitem__(
                "resumen_rumores", "mediana"
            )
        )

    def test_clip_min_mayor_que_clip_max_falla(self) -> None:
        def mutador(c: Any) -> None:
            c["aire"]["percepcion"]["clip_min"] = 500.0
            c["aire"]["percepcion"]["clip_max"] = 0.0

        self._cargar_con_override(mutador)


def _construir_pubsub(
    peer_id: str,
) -> tuple[PubSub, MembershipView, RecordingTransport]:
    vista = MembershipView(peer_id, [], t_suspect=10, t_dead=20)
    transporte = RecordingTransport(peer_id)
    pubsub = PubSub(vista, cast(Transport, transporte), POLITICAS_PUBSUB)
    return pubsub, vista, transporte


class DomainAPublisherTests(unittest.TestCase):
    def test_step_publica_un_evento_objetivo_por_tipo_y_un_subjetivo(self) -> None:
        pubsub, _vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        recibidos: list[dict[str, Any]] = []
        pubsub.agregar_callback(recibidos.append)

        publicador = DomainAPublisher(
            "santiago",
            {"robo": 0.5, "hurto": 0.5},
            PERCEPCION_DELITOS,
            pubsub,
            "127.0.0.1:7001",
            seed=126,
        )
        publicador.step(0.0)

        canales = [m["channel"] for m in recibidos]
        self.assertEqual(canales.count("objetivo"), 2)
        self.assertEqual(canales.count("subjetivo"), 1)

        subjetivo = next(m for m in recibidos if m["channel"] == "subjetivo")
        self.assertEqual(subjetivo["content"]["comuna"], "santiago")
        self.assertGreaterEqual(subjetivo["content"]["value"], 0.0)
        self.assertLessEqual(subjetivo["content"]["value"], 1.0)

    def test_misma_semilla_misma_secuencia_de_pasos(self) -> None:
        def correr() -> list[tuple[int, float]]:
            pubsub, _vista, _t = _construir_pubsub("127.0.0.1:7001")
            pubsub.subscribe("santiago")
            publicador = DomainAPublisher(
                "santiago",
                {"robo": 0.5, "hurto": 0.3},
                PERCEPCION_DELITOS,
                pubsub,
                "127.0.0.1:7001",
                seed=126,
            )
            return [
                (p.r_c, p.p_c) for t in range(10) for p in [publicador.step(float(t))]
            ]

        self.assertEqual(correr(), correr())

    def test_rumor_de_otro_peer_influye_en_p_gossip_del_siguiente_paso(self) -> None:
        pubsub, vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        publicador = DomainAPublisher(
            "santiago",
            {"robo": 0.01},
            PERCEPCION_DELITOS,
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
                "content": {"comuna": "santiago", "value": 0.99, "t": 0.0},
                "ttl": 2,
                "priority": 1,
                "origin": "127.0.0.1:7002",
            },
        }
        pubsub.handle(sobre)

        paso = publicador.step(0.0)
        self.assertAlmostEqual(paso.p_gossip, 0.99)

        # buffer se vacia tras cada paso
        paso_siguiente = publicador.step(1.0)
        self.assertEqual(paso_siguiente.p_gossip, 0.0)

    def test_no_cuenta_sus_propios_mensajes_como_rumor(self) -> None:
        pubsub, vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        publicador = DomainAPublisher(
            "santiago",
            {"robo": 0.01},
            PERCEPCION_DELITOS,
            pubsub,
            "127.0.0.1:7001",
            seed=126,
        )

        publicador.step(0.0)
        paso = publicador.step(1.0)
        self.assertEqual(paso.p_gossip, 0.0)

    def test_tick_respeta_el_intervalo_configurado(self) -> None:
        pubsub, _vista, _t = _construir_pubsub("127.0.0.1:7001")
        pubsub.subscribe("santiago")
        publicador = DomainAPublisher(
            "santiago",
            {"robo": 0.2},
            PERCEPCION_DELITOS,
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
