import random
import socket
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from civicmesh.membership.gossip import Gossip
from civicmesh.membership.view import MembershipView
from civicmesh.node import ConfigError, Node, load_config
from civicmesh.protocol import (
    ProtocolError,
    Sobre,
    codificar_sobre,
    decodificar_sobre,
)
from civicmesh.transport import Transport


def reservar_puertos(cantidad: int) -> list[int]:
    sockets: list[socket.socket] = []
    try:
        for _ in range(cantidad):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


class RecordingTransport:
    def __init__(self, peer_id: str) -> None:
        self.peer_id = peer_id
        self.sent: list[tuple[str, Sobre]] = []

    def send(self, peer_id: str, sobre: Sobre) -> None:
        self.sent.append((peer_id, sobre))


class ProtocolTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        sobre: Sobre = {
            "tipo": "gossip",
            "from": "127.0.0.1:7001",
            "payload": {
                "heartbeat": 4,
                "peers": {"127.0.0.1:7002": 3},
            },
        }

        self.assertEqual(
            decodificar_sobre(codificar_sobre(sobre)),
            sobre,
        )

    def test_codificar_valida_la_estructura(self) -> None:
        sobre = cast(
            Sobre,
            {
                "tipo": "desconocido",
                "from": "127.0.0.1:7001",
                "payload": {},
            },
        )

        with self.assertRaises(ProtocolError):
            codificar_sobre(sobre)

    def test_rechaza_valores_no_json(self) -> None:
        sobre = cast(
            Sobre,
            {
                "tipo": "gossip",
                "from": "127.0.0.1:7001",
                "payload": {"tupla": (1, 2)},
            },
        )

        with self.assertRaises(ProtocolError):
            codificar_sobre(sobre)

    def test_rechaza_nan_recibido(self) -> None:
        data = b'{"tipo":"gossip","from":"127.0.0.1:7001","payload":{"valor":NaN}}'

        with self.assertRaises(ProtocolError):
            decodificar_sobre(data)


class MembershipViewTests(unittest.TestCase):
    def test_vivos_solo_incluye_alive(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002"],
            t_suspect=10,
            t_dead=20,
        )
        self.assertEqual(vista.vivos(), [])

        vista.contacto_directo("127.0.0.1:7002", 1, 100.0)
        self.assertEqual(vista.vivos(), ["127.0.0.1:7002"])

        vista.tick(111.0)
        self.assertEqual(vista.vivos(), [])

    def test_seeds_se_deduplican_y_excluyen_al_peer_local(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            [
                "127.0.0.1:7001",
                "127.0.0.1:7002",
                "127.0.0.1:7002",
            ],
            t_suspect=10,
            t_dead=20,
        )

        self.assertEqual(vista.digest(), {"127.0.0.1:7002": 0})

    def test_elegir_excluye_dead_pero_conserva_unknown_y_suspect(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002", "127.0.0.1:7003"],
            t_suspect=10,
            t_dead=20,
        )
        vista.contacto_directo("127.0.0.1:7002", 1, 100.0)
        vista.contacto_directo("127.0.0.1:7004", 1, 110.0)
        vista.tick(121.0)

        elegidos = vista.elegir(random.Random(1), 10)

        self.assertNotIn("127.0.0.1:7002", elegidos)
        self.assertIn("127.0.0.1:7003", elegidos)
        self.assertIn("127.0.0.1:7004", elegidos)
        self.assertEqual(vista.vivos(), [])


class GossipTests(unittest.TestCase):
    def test_constructor_valida_configuracion_e_identidad(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002"],
            t_suspect=10,
            t_dead=20,
        )
        transport = cast(
            Transport,
            SimpleNamespace(peer_id="127.0.0.1:7001"),
        )

        gossip = Gossip(vista, transport, random.Random(1))
        self.assertEqual(gossip._heartbeat, 0)
        self.assertEqual(gossip._next_send, 0.0)

        with self.assertRaises(ValueError):
            Gossip(vista, transport, random.Random(1), fanout=-1)
        with self.assertRaises(ValueError):
            Gossip(vista, transport, random.Random(1), interval=0)

        otro_transport = cast(
            Transport,
            SimpleNamespace(peer_id="127.0.0.1:7003"),
        )
        with self.assertRaises(ValueError):
            Gossip(vista, otro_transport, random.Random(1))

    def test_handle_actualiza_contacto_y_digest(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002"],
            t_suspect=10,
            t_dead=20,
        )
        transport = cast(
            Transport,
            SimpleNamespace(peer_id="127.0.0.1:7001"),
        )
        gossip = Gossip(
            vista,
            transport,
            random.Random(1),
            clock=lambda: 123.0,
        )
        sobre: Sobre = {
            "tipo": "gossip",
            "from": "127.0.0.1:7002",
            "payload": {
                "heartbeat": 4,
                "peers": {"127.0.0.1:7003": 2},
            },
        }

        gossip.handle(sobre)

        self.assertEqual(vista.vivos(), ["127.0.0.1:7002"])
        self.assertEqual(
            vista.digest(),
            {
                "127.0.0.1:7002": 4,
                "127.0.0.1:7003": 2,
            },
        )

    def test_handle_rechaza_payload_invalido_sin_mutar_vista(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002"],
            t_suspect=10,
            t_dead=20,
        )
        transport = cast(
            Transport,
            SimpleNamespace(peer_id="127.0.0.1:7001"),
        )
        gossip = Gossip(vista, transport, random.Random(1))
        casos = [
            cast(
                Sobre,
                {
                    "tipo": "gossip",
                    "from": "127.0.0.1:7002",
                    "payload": {"heartbeat": True, "peers": {}},
                },
            ),
            cast(
                Sobre,
                {
                    "tipo": "gossip",
                    "from": "127.0.0.1:7002",
                    "payload": {
                        "heartbeat": 1,
                        "peers": {"sin-puerto": 2},
                    },
                },
            ),
            cast(
                Sobre,
                {
                    "tipo": "pubsub",
                    "from": "127.0.0.1:7002",
                    "payload": {"heartbeat": 1, "peers": {}},
                },
            ),
        ]

        for sobre in casos:
            with self.subTest(sobre=sobre):
                with self.assertRaises(ProtocolError):
                    gossip.handle(sobre)
                self.assertEqual(vista.digest(), {"127.0.0.1:7002": 0})

    def test_tick_respeta_intervalo_e_incrementa_heartbeat(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002"],
            t_suspect=10,
            t_dead=20,
        )
        recording_transport = RecordingTransport("127.0.0.1:7001")
        transport = cast(Transport, recording_transport)
        gossip = Gossip(
            vista,
            transport,
            random.Random(1),
            interval=1.0,
        )

        gossip.tick(10.0)
        self.assertEqual(len(recording_transport.sent), 1)
        objetivo, primer_sobre = recording_transport.sent[0]
        self.assertEqual(objetivo, "127.0.0.1:7002")
        self.assertEqual(primer_sobre["tipo"], "gossip")
        self.assertEqual(primer_sobre["from"], "127.0.0.1:7001")
        self.assertEqual(primer_sobre["payload"]["heartbeat"], 1)

        gossip.tick(10.5)
        self.assertEqual(len(recording_transport.sent), 1)

        gossip.tick(11.0)
        self.assertEqual(len(recording_transport.sent), 2)
        self.assertEqual(
            recording_transport.sent[1][1]["payload"]["heartbeat"],
            2,
        )


class TransportTests(unittest.TestCase):
    def test_rechaza_puerto_anunciado_distinto_del_bind(self) -> None:
        puerto_anunciado, puerto_bind = reservar_puertos(2)

        with self.assertRaises(ValueError):
            Transport(
                f"127.0.0.1:{puerto_anunciado}",
                ("127.0.0.1", puerto_bind),
            )

    def test_error_de_handler_no_detiene_dispatch(self) -> None:
        (puerto,) = reservar_puertos(1)
        transport = Transport(
            f"127.0.0.1:{puerto}",
            ("127.0.0.1", puerto),
        )
        self.addCleanup(transport.close)

        def handler(_sobre: Sobre) -> None:
            raise RuntimeError("fallo intencional")

        transport.register_handler("gossip", handler)
        transport._inbox.put(
            {
                "tipo": "gossip",
                "from": f"127.0.0.1:{puerto}",
                "payload": {},
            }
        )

        with self.assertLogs("civicmesh.transport", level="ERROR"):
            procesados = transport.dispatch_pending()

        self.assertEqual(procesados, 1)

    def test_handler_se_ejecuta_en_hilo_principal(self) -> None:
        puerto_emisor, puerto_receptor = reservar_puertos(2)
        emisor = Transport(
            f"127.0.0.1:{puerto_emisor}",
            ("127.0.0.1", puerto_emisor),
        )
        receptor = Transport(
            f"127.0.0.1:{puerto_receptor}",
            ("127.0.0.1", puerto_receptor),
        )
        self.addCleanup(emisor.close)
        self.addCleanup(receptor.close)

        hilo_principal = threading.get_ident()
        llamadas: list[tuple[int, int]] = []
        receptor.register_handler(
            "gossip",
            lambda sobre: llamadas.append(
                (threading.get_ident(), cast(int, sobre["payload"]["heartbeat"]))
            ),
        )
        receptor.start()

        sobre: Sobre = {
            "tipo": "gossip",
            "from": f"127.0.0.1:{puerto_emisor}",
            "payload": {"heartbeat": 7},
        }
        emisor.send(f"127.0.0.1:{puerto_receptor}", sobre)

        limite = time.monotonic() + 1.0
        while time.monotonic() < limite and not llamadas:
            receptor.dispatch_pending()
            if not llamadas:
                time.sleep(0.01)

        self.assertEqual(llamadas, [(hilo_principal, 7)])

        receptor.close()
        self.assertIsNotNone(receptor._receiver_thread)
        assert receptor._receiver_thread is not None
        self.assertFalse(receptor._receiver_thread.is_alive())


class NodeTests(unittest.TestCase):
    def test_carga_peer_desde_yaml_compartido(self) -> None:
        config_path = Path(__file__).parents[1] / "config.example.yaml"

        config = load_config(config_path, "peer-1")

        self.assertEqual(config.bind, ("0.0.0.0", 7001))
        self.assertEqual(config.advertise, "127.0.0.1:7001")
        self.assertEqual(config.seeds, ("127.0.0.1:7002",))
        self.assertEqual(config.gossip_fanout, 1)
        self.assertEqual(config.random_seed, 126)

        with self.assertRaises(ConfigError):
            load_config(config_path, "peer-inexistente")

    def test_run_once_drena_antes_de_ejecutar_ticks(self) -> None:
        eventos: list[tuple[str, float | int]] = []
        transport = cast(
            Transport,
            SimpleNamespace(
                dispatch_pending=lambda: eventos.append(("dispatch", 2)) or 2
            ),
        )
        component = SimpleNamespace(
            tick=lambda now: eventos.append(("tick", now)),
        )
        node = Node(
            transport,
            [component],
            loop_interval=0.05,
            clock=lambda: 42.0,
        )

        self.assertEqual(node.run_once(), 2)
        self.assertEqual(eventos, [("dispatch", 2), ("tick", 42.0)])


class IntegrationTests(unittest.TestCase):
    def test_tres_nodos_descubren_la_malla(self) -> None:
        puertos = reservar_puertos(3)
        peer_ids = [f"127.0.0.1:{puerto}" for puerto in puertos]
        vistas: list[MembershipView] = []
        transports: list[Transport] = []
        nodes: list[Node] = []

        for indice, peer_id in enumerate(peer_ids):
            seed = peer_ids[(indice + 1) % len(peer_ids)]
            transport = Transport(peer_id, ("127.0.0.1", puertos[indice]))
            vista = MembershipView(
                peer_id,
                [seed],
                t_suspect=0.5,
                t_dead=1.0,
            )
            gossip = Gossip(
                vista,
                transport,
                random.Random(indice),
                fanout=1,
                interval=0.02,
            )
            transport.register_handler("gossip", gossip.handle)
            nodes.append(Node(transport, [gossip], loop_interval=0.005))
            transports.append(transport)
            vistas.append(vista)

        threads = [threading.Thread(target=node.run) for node in nodes]
        try:
            for thread in threads:
                thread.start()

            limite = time.monotonic() + 2.0
            while time.monotonic() < limite:
                if all(len(vista.digest()) == 2 for vista in vistas):
                    break
                time.sleep(0.01)

            self.assertTrue(
                all(len(vista.digest()) == 2 for vista in vistas),
                [vista.digest() for vista in vistas],
            )
            self.assertTrue(all(vista.vivos() for vista in vistas))
        finally:
            for node in nodes:
                node.stop()
            for thread in threads:
                thread.join(timeout=1.0)
            for transport in transports:
                transport.close()


if __name__ == "__main__":
    unittest.main()
