import random
import socket
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from civicmesh.membership.gossip import Gossip
from civicmesh.membership.view import MembershipView
from civicmesh.node import ConfigError, Node, load_config
from civicmesh.protocol import (
    ProtocolError,
    Sobre,
    codificar_sobre,
    decodificar_sobre,
)
from civicmesh.pubsub import PubSub, SubscriptionManager, should_forward
from civicmesh.transport import Transport, resolve_endpoints


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
                "topics": ["santiago"],
                "peers": {
                    "127.0.0.1:7002": {
                        "heartbeat": 3,
                        "topics": ["providencia"],
                    }
                },
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

        vista.contacto_directo("127.0.0.1:7002", 1, [], 100.0)
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

        self.assertEqual(
            vista.digest(),
            {"127.0.0.1:7002": {"heartbeat": 0, "topics": []}},
        )

    def test_elegir_excluye_dead_pero_conserva_unknown_y_suspect(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002", "127.0.0.1:7003"],
            t_suspect=10,
            t_dead=20,
        )
        vista.contacto_directo("127.0.0.1:7002", 1, [], 100.0)
        vista.contacto_directo("127.0.0.1:7004", 1, [], 110.0)
        vista.tick(121.0)

        elegidos = vista.elegir(random.Random(1), 10)

        self.assertNotIn("127.0.0.1:7002", elegidos)
        self.assertIn("127.0.0.1:7003", elegidos)
        self.assertIn("127.0.0.1:7004", elegidos)
        self.assertEqual(vista.vivos(), [])

    def test_topics_se_aceptan_solo_con_heartbeat_mayor(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002"],
            t_suspect=10,
            t_dead=20,
        )
        vista.contacto_directo(
            "127.0.0.1:7002",
            2,
            ["santiago", "santiago", ""],
            100.0,
        )

        vista.contacto_directo(
            "127.0.0.1:7002",
            2,
            ["descartado"],
            200.0,
        )
        vista.merge_digest(
            {
                "127.0.0.1:7002": {
                    "heartbeat": 1,
                    "topics": ["tambien-descartado"],
                }
            }
        )
        self.assertEqual(
            vista.topics_de("127.0.0.1:7002"),
            ["santiago", "santiago", ""],
        )
        self.assertEqual(dict(vista.items())["127.0.0.1:7002"]["last_seen"], 100.0)

        vista.merge_digest(
            {
                "127.0.0.1:7002": {
                    "heartbeat": 3,
                    "topics": ["providencia"],
                }
            }
        )
        self.assertEqual(vista.topics_de("127.0.0.1:7002"), ["providencia"])

    def test_topics_propios_y_consultas_devuelven_copias(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            [],
            t_suspect=10,
            t_dead=20,
        )
        topics = ["santiago"]
        vista.set_topics(topics)
        topics.append("providencia")

        consulta = vista.topics_de("127.0.0.1:7001")
        consulta.append("nunoa")

        self.assertEqual(vista.topics_de("127.0.0.1:7001"), ["santiago"])
        self.assertEqual(vista.topics_de("127.0.0.1:7999"), [])


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
                "topics": ["santiago"],
                "peers": {
                    "127.0.0.1:7003": {
                        "heartbeat": 2,
                        "topics": ["providencia"],
                    }
                },
            },
        }

        gossip.handle(sobre)

        self.assertEqual(vista.vivos(), ["127.0.0.1:7002"])
        self.assertEqual(
            vista.digest(),
            {
                "127.0.0.1:7002": {
                    "heartbeat": 4,
                    "topics": ["santiago"],
                },
                "127.0.0.1:7003": {
                    "heartbeat": 2,
                    "topics": ["providencia"],
                },
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
                    "payload": {"heartbeat": True, "topics": [], "peers": {}},
                },
            ),
            cast(
                Sobre,
                {
                    "tipo": "gossip",
                    "from": "127.0.0.1:7002",
                    "payload": {
                        "heartbeat": 1,
                        "topics": [],
                        "peers": {
                            "sin-puerto": {"heartbeat": 2, "topics": []}
                        },
                    },
                },
            ),
            cast(
                Sobre,
                {
                    "tipo": "gossip",
                    "from": "127.0.0.1:7002",
                    "payload": {
                        "heartbeat": 1,
                        "topics": [1],
                        "peers": {},
                    },
                },
            ),
            cast(
                Sobre,
                {
                    "tipo": "gossip",
                    "from": "127.0.0.1:7002",
                    "payload": {
                        "heartbeat": 1,
                        "topics": [],
                        "peers": {
                            "127.0.0.1:7003": {
                                "heartbeat": 2,
                                "topics": "santiago",
                            }
                        },
                    },
                },
            ),
            cast(
                Sobre,
                {
                    "tipo": "pubsub",
                    "from": "127.0.0.1:7002",
                    "payload": {"heartbeat": 1, "topics": [], "peers": {}},
                },
            ),
        ]

        for sobre in casos:
            with self.subTest(sobre=sobre):
                with self.assertRaises(ProtocolError):
                    gossip.handle(sobre)
                self.assertEqual(
                    vista.digest(),
                    {"127.0.0.1:7002": {"heartbeat": 0, "topics": []}},
                )

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
        vista.set_topics(["santiago"])

        gossip.tick(10.0)
        self.assertEqual(len(recording_transport.sent), 1)
        objetivo, primer_sobre = recording_transport.sent[0]
        self.assertEqual(objetivo, "127.0.0.1:7002")
        self.assertEqual(primer_sobre["tipo"], "gossip")
        self.assertEqual(primer_sobre["from"], "127.0.0.1:7001")
        self.assertEqual(primer_sobre["payload"]["heartbeat"], 1)
        self.assertEqual(primer_sobre["payload"]["topics"], ["santiago"])

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

    def test_cachea_resolucion_del_remitente_por_peer_id(self) -> None:
        puerto_emisor, puerto_receptor = reservar_puertos(2)
        peer_emisor = f"127.0.0.1:{puerto_emisor}"
        peer_receptor = f"127.0.0.1:{puerto_receptor}"
        emisor = Transport(peer_emisor, ("127.0.0.1", puerto_emisor))
        receptor = Transport(peer_receptor, ("127.0.0.1", puerto_receptor))
        self.addCleanup(emisor.close)
        self.addCleanup(receptor.close)

        recibidos: list[int] = []
        receptor.register_handler(
            "gossip",
            lambda sobre: recibidos.append(
                cast(int, sobre["payload"]["heartbeat"])
            ),
        )

        with patch(
            "civicmesh.transport.resolve_endpoints",
            wraps=resolve_endpoints,
        ) as resolver:
            receptor.start()
            for heartbeat in (1, 2):
                emisor.send(
                    peer_receptor,
                    {
                        "tipo": "gossip",
                        "from": peer_emisor,
                        "payload": {"heartbeat": heartbeat},
                    },
                )

            limite = time.monotonic() + 1.0
            while time.monotonic() < limite and len(recibidos) < 2:
                receptor.dispatch_pending()
                if len(recibidos) < 2:
                    time.sleep(0.01)

            self.assertEqual(recibidos, [1, 2])
            resolver.assert_called_once_with(peer_emisor)


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
            vista.set_topics([f"topic-{indice}"])
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
                if all(
                    len(vista.digest()) == 2
                    and all(
                        vista.topics_de(pid) == [f"topic-{indice}"]
                        for indice, pid in enumerate(peer_ids)
                    )
                    for vista in vistas
                ):
                    break
                time.sleep(0.01)

            self.assertTrue(
                all(len(vista.digest()) == 2 for vista in vistas),
                [vista.digest() for vista in vistas],
            )
            self.assertTrue(all(vista.vivos() for vista in vistas))
            for vista in vistas:
                for indice, pid in enumerate(peer_ids):
                    self.assertEqual(vista.topics_de(pid), [f"topic-{indice}"])
        finally:
            for node in nodes:
                node.stop()
            for thread in threads:
                thread.join(timeout=1.0)

    def test_dos_peers_dejan_de_verse_al_bloquearse_mutuamente(self) -> None:
        puertos = reservar_puertos(2)
        peer_ids = [f"127.0.0.1:{puerto}" for puerto in puertos]
        vistas: list[MembershipView] = []
        transports: list[Transport] = []
        nodes: list[Node] = []

        for indice, peer_id in enumerate(peer_ids):
            otro_peer = peer_ids[1 - indice]
            transport = Transport(peer_id, ("127.0.0.1", puertos[indice]))
            vista = MembershipView(
                peer_id,
                [otro_peer],
                t_suspect=0.1,
                t_dead=0.2,
            )
            gossip = Gossip(
                vista,
                transport,
                random.Random(indice),
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

            limite = time.monotonic() + 1.0
            while time.monotonic() < limite and not all(
                vista.vivos() for vista in vistas
            ):
                time.sleep(0.01)
            self.assertTrue(all(vista.vivos() for vista in vistas))

            transports[0].blocked_peers.add(peer_ids[1])
            transports[1].blocked_peers.add(peer_ids[0])

            limite = time.monotonic() + 1.0
            while time.monotonic() < limite and not all(
                dict(vista.items())[peer_ids[1 - indice]]["estado"] == "dead"
                for indice, vista in enumerate(vistas)
            ):
                time.sleep(0.01)
            self.assertTrue(
                all(
                    dict(vista.items())[peer_ids[1 - indice]]["estado"] == "dead"
                    for indice, vista in enumerate(vistas)
                )
            )
        finally:
            for node in nodes:
                node.stop()
            for thread in threads:
                thread.join(timeout=1.0)


class PubSubTests(unittest.TestCase):
    def test_should_forward_bloquea_mensajes_expirados(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002"],
            t_suspect=10,
            t_dead=20,
        )
        vista.contacto_directo("127.0.0.1:7002", 1, [], 100.0)

        # TTL = 0 (expirado)
        msg_expirado = {
            "id": "msg-1",
            "topic": "santiago",
            "channel": "objetivo",
            "content": "calidad_aire: mala",
            "ttl": 0,
            "priority": 1,
            "origin": "127.0.0.1:7001",
        }
        self.assertFalse(should_forward(msg_expirado, "santiago", vista))

        # TTL < 0
        msg_negativo = dict(msg_expirado)
        msg_negativo["ttl"] = -1
        self.assertFalse(should_forward(msg_negativo, "santiago", vista))

        # TTL valido (> 0)
        msg_valido = dict(msg_expirado)
        msg_valido["ttl"] = 3
        self.assertTrue(should_forward(msg_valido, "santiago", vista))

    def test_should_forward_valida_prioridad(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002"],
            t_suspect=10,
            t_dead=20,
        )
        vista.contacto_directo("127.0.0.1:7002", 1, [], 100.0)

        msg_prioridad_invalida = {
            "id": "msg-2",
            "topic": "santiago",
            "channel": "subjetivo",
            "content": "alerta",
            "ttl": 2,
            "priority": 0,
            "origin": "127.0.0.1:7001",
        }
        self.assertFalse(should_forward(msg_prioridad_invalida, "santiago", vista))

    def test_should_forward_evita_flooding_sin_interesados_o_peers_vivos(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002"],
            t_suspect=10,
            t_dead=20,
        )

        msg = {
            "id": "msg-3",
            "topic": "santiago",
            "channel": "objetivo",
            "content": "ok",
            "ttl": 2,
            "priority": 1,
            "origin": "127.0.0.1:7001",
        }

        # Sin peers vivos en la vista local -> False
        self.assertFalse(should_forward(msg, "santiago", vista))

        # Peer vivo pero sin interés registrado en suscripciones -> False
        vista.contacto_directo("127.0.0.1:7002", 1, [], 100.0)
        subs = SubscriptionManager()
        subs.registrar_suscripcion_peer("127.0.0.1:7002", ["las_condes"])
        self.assertFalse(should_forward(msg, "santiago", vista, subs))

        # Con suscripción coincidente -> True
        subs.registrar_suscripcion_peer("127.0.0.1:7002", ["santiago"])
        self.assertTrue(should_forward(msg, "santiago", vista, subs))

    def test_adyacencia_espacial_en_suscripciones(self) -> None:
        subs = SubscriptionManager()
        # Peer 2 suscrito a Providencia (adyacente a Santiago)
        subs.registrar_suscripcion_peer("127.0.0.1:7002", ["providencia"])

        # Mensaje publicado en Santiago debe ser de interés para Providencia
        self.assertTrue(subs.esta_interesado_peer("127.0.0.1:7002", "santiago"))
        # Mensaje publicado en Maipú NO es adyacente a Providencia directamente
        self.assertFalse(subs.esta_interesado_peer("127.0.0.1:7002", "maipu"))

    def test_pubsub_componente_y_deduplicacion(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002"],
            t_suspect=10,
            t_dead=20,
        )
        rec = RecordingTransport("127.0.0.1:7001")
        transport = cast(Transport, rec)
        pubsub = PubSub(vista, transport)

        recibidos: list[dict] = []
        pubsub.subscribe("santiago")
        pubsub.agregar_callback(lambda m: recibidos.append(m))

        # Publicar localmente
        msg_id = pubsub.publish("santiago", {"pm25": 12.5}, channel="objetivo")
        self.assertIsNotNone(msg_id)
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0]["content"], {"pm25": 12.5})

        # Recibir sobre duplicado
        sobre_duplicado: Sobre = {
            "tipo": "pubsub",
            "from": "127.0.0.1:7002",
            "payload": {
                "id": msg_id,
                "topic": "santiago",
                "channel": "objetivo",
                "content": {"pm25": 12.5},
                "ttl": 3,
                "priority": 1,
                "origin": "127.0.0.1:7001",
            },
        }

        pubsub.handle(sobre_duplicado)
        # No se debe procesar de nuevo por la deduplicación
        self.assertEqual(len(recibidos), 1)

    def test_pubsub_fanout_seleccion_aleatoria(self) -> None:
        vista = MembershipView(
            "127.0.0.1:7001",
            ["127.0.0.1:7002", "127.0.0.1:7003", "127.0.0.1:7004"],
            t_suspect=10,
            t_dead=20,
        )
        vista.contacto_directo("127.0.0.1:7002", 1, [], 100.0)
        vista.contacto_directo("127.0.0.1:7003", 1, [], 100.0)
        vista.contacto_directo("127.0.0.1:7004", 1, [], 100.0)

        rec = RecordingTransport("127.0.0.1:7001")
        transport = cast(Transport, rec)
        # Configurar fanout=1 y rng determinista
        rng = random.Random(42)
        pubsub = PubSub(vista, transport, fanout=1, rng=rng)

        pubsub.publish("santiago", "alerta", channel="objetivo")
        self.assertEqual(len(rec.sent), 1)
        # Debe enviar solo a 1 destinatario debido al fanout
        destinatario = rec.sent[0][0]
        self.assertIn(
            destinatario, ["127.0.0.1:7002", "127.0.0.1:7003", "127.0.0.1:7004"]
        )


if __name__ == "__main__":
    unittest.main()
