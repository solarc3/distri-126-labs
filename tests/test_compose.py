import unittest
from pathlib import Path

import yaml

from civicmesh.node import load_config

REPO_ROOT = Path(__file__).parents[1]


class ComposeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compose = yaml.safe_load(
            (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        )

    def test_base_es_extension_y_no_un_servicio_ejecutable(self) -> None:
        self.assertIn("x-peer-base", self.compose)
        self.assertNotIn("peer-base", self.compose["services"])

    def test_peers_entregan_config_y_peer_al_entrypoint(self) -> None:
        services = self.compose["services"]
        for peer in ("peer-1", "peer-2", "peer-3"):
            with self.subTest(peer=peer):
                self.assertEqual(
                    services[peer]["command"],
                    ["--config", "/app/config.yaml", "--peer", peer],
                )

    def test_publicadores_y_frontend_usan_sus_entrypoints_reales(self) -> None:
        services = self.compose["services"]
        for dominio in ("delitos", "aire"):
            with self.subTest(dominio=dominio):
                publisher = services[f"publisher-{dominio}"]
                self.assertEqual(
                    publisher["entrypoint"],
                    ["python", "-m", "civicmesh.domains.publisher_main"],
                )
                self.assertIn("--peer", publisher["command"])
                self.assertIn("--dominio", publisher["command"])
                self.assertIn("--comuna", publisher["command"])
                self.assertNotIn("--domain", publisher["command"])

        self.assertEqual(
            services["frontend"]["entrypoint"],
            ["python", "scripts/frontend.py"],
        )
        self.assertIn("--metrics", services["frontend"]["command"])

    def test_config_compose_define_todos_los_peers_con_dns_docker(self) -> None:
        config_path = REPO_ROOT / "config.compose.yaml"
        peers = (
            "peer-1",
            "peer-2",
            "peer-3",
            "publisher-delitos",
            "publisher-aire",
        )

        for peer in peers:
            with self.subTest(peer=peer):
                config = load_config(config_path, peer)
                self.assertEqual(config.bind, ("0.0.0.0", 7000))
                self.assertEqual(config.advertise, f"{peer}:7000")


if __name__ == "__main__":
    unittest.main()
