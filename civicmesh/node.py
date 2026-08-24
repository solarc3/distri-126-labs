"""Punto de entrada y coordinador de los componentes de un peer."""

import argparse
import logging
import random
import signal
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol, TypeAlias, cast

import yaml

from civicmesh.membership.gossip import Gossip
from civicmesh.membership.view import MembershipView
from civicmesh.protocol import PeerId
from civicmesh.transport import Endpoint, EndpointError, Transport, parse_endpoint

logger = logging.getLogger(__name__)

Clock: TypeAlias = Callable[[], float]


class Component(Protocol):
    def tick(self, now: float) -> None: ...


class ConfigError(ValueError):
    """Indica que config.yaml no cumple el contrato del nodo."""


@dataclass(frozen=True)
class NodeConfig:
    bind: Endpoint
    advertise: PeerId
    seeds: tuple[PeerId, ...]
    gossip_fanout: int
    gossip_interval: float
    t_suspect: float
    t_dead: float
    random_seed: int
    loop_interval: float


def _mapping(valor: object, ruta: str) -> dict[str, object]:
    if not isinstance(valor, dict):
        raise ConfigError(f"{ruta} debe ser un objeto")
    if not all(isinstance(clave, str) for clave in valor):
        raise ConfigError(f"{ruta} solo puede tener claves de texto")
    return cast(dict[str, object], valor)


def _text(valor: object, ruta: str) -> str:
    if not isinstance(valor, str) or not valor:
        raise ConfigError(f"{ruta} debe ser texto no vacio")
    return valor


def _integer(valor: object, ruta: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ConfigError(f"{ruta} debe ser un entero")
    return valor


def _number(valor: object, ruta: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ConfigError(f"{ruta} debe ser un numero")
    return float(valor)


def _parse_config_endpoint(valor: object, ruta: str) -> tuple[str, Endpoint]:
    peer_id = _text(valor, ruta)
    try:
        endpoint = parse_endpoint(peer_id)
    except EndpointError as error:
        raise ConfigError(f"{ruta}: {error}") from error
    return peer_id, endpoint


def load_config(path: Path, peer_name: str) -> NodeConfig:
    try:
        contenido = path.read_text(encoding="utf-8")
        raw: object = yaml.safe_load(contenido)
    except OSError as error:
        raise ConfigError(f"no se pudo leer {path}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"YAML invalido en {path}") from error

    root = _mapping(raw, "config")
    network = _mapping(root.get("network"), "network")
    peers = _mapping(network.get("peers"), "network.peers")
    if peer_name not in peers:
        raise ConfigError(f"peer desconocido: {peer_name}")
    peer = _mapping(peers[peer_name], f"network.peers.{peer_name}")

    _bind_text, bind = _parse_config_endpoint(
        peer.get("bind"),
        f"network.peers.{peer_name}.bind",
    )
    advertise, advertise_endpoint = _parse_config_endpoint(
        peer.get("advertise"),
        f"network.peers.{peer_name}.advertise",
    )
    if advertise_endpoint[0] == "0.0.0.0":
        raise ConfigError("advertise no puede usar 0.0.0.0")
    if bind[1] != advertise_endpoint[1]:
        raise ConfigError("bind y advertise deben usar el mismo puerto")

    seeds_raw = peer.get("seeds", [])
    if not isinstance(seeds_raw, list):
        raise ConfigError(f"network.peers.{peer_name}.seeds debe ser una lista")
    seeds: list[PeerId] = []
    for indice, seed_raw in enumerate(seeds_raw):
        seed, _endpoint = _parse_config_endpoint(
            seed_raw,
            f"network.peers.{peer_name}.seeds[{indice}]",
        )
        if seed == advertise:
            raise ConfigError("un peer no puede usarse a si mismo como seed")
        if seed not in seeds:
            seeds.append(seed)

    gossip = _mapping(root.get("gossip", {}), "gossip")
    fanout = _integer(gossip.get("fanout", 1), "gossip.fanout")
    interval = _number(
        gossip.get("interval_seconds", 1.0),
        "gossip.interval_seconds",
    )
    t_suspect = _number(
        gossip.get("suspect_after_seconds", 10.0),
        "gossip.suspect_after_seconds",
    )
    t_dead = _number(
        gossip.get("dead_after_seconds", 20.0),
        "gossip.dead_after_seconds",
    )
    random_seed = _integer(gossip.get("random_seed", 0), "gossip.random_seed")
    if fanout < 0:
        raise ConfigError("gossip.fanout no puede ser negativo")
    if interval <= 0:
        raise ConfigError("gossip.interval_seconds debe ser positivo")
    if t_suspect <= 0 or t_dead <= t_suspect:
        raise ConfigError("los timeouts deben cumplir 0 < suspect_after < dead_after")

    node = _mapping(root.get("node", {}), "node")
    loop_interval = _number(
        node.get("loop_interval_seconds", 0.05),
        "node.loop_interval_seconds",
    )
    if loop_interval <= 0:
        raise ConfigError("node.loop_interval_seconds debe ser positivo")

    return NodeConfig(
        bind=bind,
        advertise=advertise,
        seeds=tuple(seeds),
        gossip_fanout=fanout,
        gossip_interval=interval,
        t_suspect=t_suspect,
        t_dead=t_dead,
        random_seed=random_seed,
        loop_interval=loop_interval,
    )


class Node:
    """Coordina transporte y componentes sin conocer sus protocolos internos."""

    def __init__(
        self,
        transport: Transport,
        components: Sequence[Component],
        *,
        loop_interval: float,
        clock: Clock = time.monotonic,
    ) -> None:
        if loop_interval <= 0:
            raise ValueError("el intervalo del loop debe ser positivo")

        self._transport = transport
        self._components = tuple(components)
        self._loop_interval = loop_interval
        self._clock = clock
        self._stop_event = Event()

    def run_once(self) -> int:
        procesados = self._transport.dispatch_pending()
        now = self._clock()
        for component in self._components:
            component.tick(now)
        return procesados

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        self._transport.start()
        try:
            while not self._stop_event.is_set():
                self.run_once()
                self._stop_event.wait(self._loop_interval)
        finally:
            self._transport.close()


def build_node(config: NodeConfig) -> Node:
    transport = Transport(config.advertise, config.bind)
    vista = MembershipView(
        config.advertise,
        config.seeds,
        t_suspect=config.t_suspect,
        t_dead=config.t_dead,
    )
    gossip = Gossip(
        vista,
        transport,
        random.Random(config.random_seed),
        fanout=config.gossip_fanout,
        interval=config.gossip_interval,
    )
    transport.register_handler("gossip", gossip.handle)
    return Node(
        transport,
        [gossip],
        loop_interval=config.loop_interval,
    )


def main(args: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ejecuta un peer CivicMesh")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--peer", required=True)
    parsed = parser.parse_args(args)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        config = load_config(parsed.config, parsed.peer)
        node = build_node(config)
    except (ConfigError, OSError, ValueError) as error:
        parser.error(str(error))

    def solicitar_cierre(_signum: int, _frame: object) -> None:
        node.stop()

    signal.signal(signal.SIGINT, solicitar_cierre)
    signal.signal(signal.SIGTERM, solicitar_cierre)
    logger.info("peer iniciado: %s", config.advertise)
    node.run()


if __name__ == "__main__":
    main()
