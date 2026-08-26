import socket
import tempfile
import unittest
from pathlib import Path

import yaml

from civicmesh.domains.publisher_main import PublisherSetupError, build_publisher_node

AIR_CACHE_DIR = Path(__file__).parents[1] / "data" / "air_quality"

NETWORK_CONFIG_BASE = {
    "gossip": {
        "fanout": 1,
        "interval_seconds": 1.0,
        "suspect_after_seconds": 10.0,
        "dead_after_seconds": 20.0,
        "random_seed": 126,
    },
    "pubsub": {
        "channels": {
            "objetivo": {"ttl": 5, "priority": 2},
            "subjetivo": {"ttl": 3, "priority": 1},
        }
    },
    "node": {"loop_interval_seconds": 0.05},
}

GENERADORES_CONFIG = {
    "seed": 126,
    "delitos": {
        "tasas": {"santiago": {"robo": 0.5}},
        "percepcion": {
            "alpha": 0.8,
            "beta0": -1.0,
            "beta1": 0.4,
            "beta2": 0.8,
            "sigma_eps": 0.1,
            "resumen_rumores": "promedio",
            "usar_sigmoide": True,
        },
    },
    "aire": {
        "comunas": ["santiago"],
        "percepcion": {
            "alpha": 0.85,
            "gamma": 0.6,
            "delta": 0.3,
            "sigma_eps": 2.0,
            "clip_min": 0.0,
            "clip_max": 500.0,
            "resumen_rumores": "promedio",
        },
        "extrapolacion": {"metodo": "idw", "potencia": 2.0},
    },
}


def _puerto_libre() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


class BuildPublisherNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directorio = tempfile.TemporaryDirectory()
        directorio = Path(self._directorio.name)
        self.addCleanup(self._directorio.cleanup)

        puerto = _puerto_libre()
        network = {
            **NETWORK_CONFIG_BASE,
            "network": {
                "peers": {
                    "publicador-test": {
                        "bind": f"0.0.0.0:{puerto}",
                        "advertise": f"127.0.0.1:{puerto}",
                        "seeds": [],
                    }
                }
            },
        }
        self.config_path = directorio / "network.yaml"
        self.config_path.write_text(yaml.safe_dump(network), encoding="utf-8")

        self.generadores_path = directorio / "generadores.yaml"
        self.generadores_path.write_text(
            yaml.safe_dump(GENERADORES_CONFIG), encoding="utf-8"
        )

    def test_dominio_delitos_comuna_sin_tasas_configuradas_falla(self) -> None:
        with self.assertRaises(PublisherSetupError):
            build_publisher_node(
                self.config_path,
                "publicador-test",
                self.generadores_path,
                "delitos",
                "las_condes",
                AIR_CACHE_DIR,
                intervalo_segundos=1.0,
                loop_air=True,
            )

    def test_dominio_aire_comuna_no_configurada_falla(self) -> None:
        # Antes del fix, una comuna fuera de aire.comunas no se validaba antes
        # de construir el publicador: el error solo aparecia mas tarde, dentro
        # del loop del Node, como un CoordenadasError sin capturar.
        with self.assertRaises(PublisherSetupError):
            build_publisher_node(
                self.config_path,
                "publicador-test",
                self.generadores_path,
                "aire",
                "las_condes",
                AIR_CACHE_DIR,
                intervalo_segundos=1.0,
                loop_air=True,
            )

    def test_dominio_aire_comuna_configurada_construye_el_nodo(self) -> None:
        node = build_publisher_node(
            self.config_path,
            "publicador-test",
            self.generadores_path,
            "aire",
            "santiago",
            AIR_CACHE_DIR,
            intervalo_segundos=1.0,
            loop_air=True,
        )
        self.addCleanup(node._transport.close)
        self.assertIsNotNone(node)


if __name__ == "__main__":
    unittest.main()
