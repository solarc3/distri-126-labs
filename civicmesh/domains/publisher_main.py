import argparse
import logging
import random
import signal
from pathlib import Path
from typing import Literal, cast

from civicmesh.comunas import normalizar_tópico
from civicmesh.domains.air_quality_cache import cargar_series_directorio
from civicmesh.domains.config import GeneradoresConfigError, load_generadores_config
from civicmesh.domains.domain_a import DomainAPublisher
from civicmesh.domains.domain_b import DomainBPublisher
from civicmesh.domains.extrapolacion import ProveedorAire
from civicmesh.domains.replay import ReplayAire
from civicmesh.membership.gossip import Gossip
from civicmesh.membership.view import MembershipView
from civicmesh.metrics import EscribirMetricas
from civicmesh.node import ConfigError, Node, load_config
from civicmesh.pubsub import PoliticasCanales, PubSub
from civicmesh.transport import Transport

logger = logging.getLogger(__name__)

Dominio = Literal["delitos", "aire"]

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GENERADORES_PATH = _REPO_ROOT / "generadores.example.yaml"
DEFAULT_AIR_CACHE_DIR = _REPO_ROOT / "data" / "air_quality"


class PublisherSetupError(ValueError):
    """indica que no fue posible armar el publicador con la configuracion dada"""


class EstadoProceso:
    """Vuelca el estado de la vista de membresia como metrica periodicamente."""

    def __init__(
        self,
        vista: MembershipView,
        metricas: EscribirMetricas,
        intervalo_segundos: float,
    ) -> None:
        self._vista = vista
        self._metricas = metricas
        self._intervalo = intervalo_segundos
        self._next_send = 0.0

    def tick(self, now: float) -> None:
        if now < self._next_send:
            return
        self._next_send = now + self._intervalo
        suspect = sum(1 for _pid, e in self._vista.items() if e["estado"] == "suspect")
        muertos = sum(1 for _pid, e in self._vista.items() if e["estado"] == "dead")
        self._metricas.estado(
            len(self._vista.vivos()),
            suspect,
            muertos,
            len(self._vista),
        )


def build_publisher_node(
    config_path: Path,
    peer_name: str,
    generadores_path: Path,
    dominio: Dominio,
    comuna: str,
    air_cache_dir: Path,
    intervalo_segundos: float,
    loop_air: bool,
    default_dt: float = 1.0,
    run_id: str = "local",
    metrics_dir: Path | None = None,
    t_suspect: float | None = None,
    t_dead: float | None = None,
    gossip_fanout: int | None = None,
    politicas: PoliticasCanales | None = None,
) -> Node:
    network_config = load_config(config_path, peer_name)
    generadores = load_generadores_config(generadores_path)

    transport = Transport(network_config.advertise, network_config.bind)
    vista = MembershipView(
        network_config.advertise,
        network_config.seeds,
        t_suspect=network_config.t_suspect if t_suspect is None else t_suspect,
        t_dead=network_config.t_dead if t_dead is None else t_dead,
    )
    rng = random.Random(network_config.random_seed)
    gossip = Gossip(
        vista,
        transport,
        rng,
        fanout=network_config.gossip_fanout if gossip_fanout is None else gossip_fanout,
        interval=network_config.gossip_interval,
    )
    pubsub = PubSub(
        vista,
        transport,
        network_config.pubsub_policies if politicas is None else politicas,
        rng=rng,
    )
    transport.register_handler("gossip", gossip.handle)
    transport.register_handler("pubsub", pubsub.handle)
    pubsub.subscribe(comuna)

    metricas = EscribirMetricas(
        run_id,
        network_config.advertise,
        metrics_dir or Path(".") / run_id / "metrics",
    )
    comuna_normalizada = normalizar_tópico(comuna)
    domain_component: DomainAPublisher | DomainBPublisher
    if dominio == "delitos":
        tasas_comuna = generadores["delitos"]["tasas"].get(comuna_normalizada)
        if tasas_comuna is None:
            raise PublisherSetupError(
                f"no hay tasas configuradas para la comuna {comuna}"
            )
        domain_component = DomainAPublisher(
            comuna=comuna,
            tasas=tasas_comuna,
            percepcion=generadores["delitos"]["percepcion"],
            pubsub=pubsub,
            peer_id=network_config.advertise,
            seed=generadores["seed"],
            dt=default_dt,
            intervalo_segundos=intervalo_segundos,
            metricas=metricas,
        )
    else:
        if comuna_normalizada not in generadores["aire"]["comunas"]:
            raise PublisherSetupError(
                f"la comuna {comuna} no esta en aire.comunas de generadores"
            )
        series = cargar_series_directorio(air_cache_dir)
        extrapolacion = generadores["aire"]["extrapolacion"]
        proveedor = ProveedorAire(
            series,
            extrapolacion["metodo"],
            extrapolacion["potencia"],
        )
        replay = ReplayAire(comuna, proveedor, loop=loop_air)
        domain_component = DomainBPublisher(
            comuna=comuna,
            replay=replay,
            percepcion=generadores["aire"]["percepcion"],
            pubsub=pubsub,
            peer_id=network_config.advertise,
            seed=generadores["seed"],
            dt=default_dt,
            intervalo_segundos=intervalo_segundos,
            metricas=metricas,
        )

    return Node(
        transport,
        [gossip, pubsub, domain_component, EstadoProceso(vista, metricas, 1.0)],
        loop_interval=network_config.loop_interval,
    )


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="ejecuta un publicador de dominio CivicMesh"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--peer", required=True)
    parser.add_argument("--generadores", type=Path, default=DEFAULT_GENERADORES_PATH)
    parser.add_argument("--dominio", choices=("delitos", "aire"), required=True)
    parser.add_argument("--comuna", required=True)
    parser.add_argument("--air-cache-dir", type=Path, default=DEFAULT_AIR_CACHE_DIR)
    parser.add_argument("--intervalo-segundos", type=float, default=1.0)
    parser.add_argument("--dt", type=float, default=1.0)
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--metrics-dir", type=Path, default=None)
    parser.add_argument(
        "--no-loop-air",
        action="store_true",
        help="no reiniciar el replay de aire al llegar al final de la serie cacheada",
    )
    parsed = parser.parse_args(args)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        node = build_publisher_node(
            parsed.config,
            parsed.peer,
            parsed.generadores,
            cast(Dominio, parsed.dominio),
            parsed.comuna,
            parsed.air_cache_dir,
            parsed.intervalo_segundos,
            not parsed.no_loop_air,
            default_dt=parsed.dt,
            run_id=parsed.run_id,
            metrics_dir=parsed.metrics_dir,
        )
    except (
        ConfigError,
        GeneradoresConfigError,
        PublisherSetupError,
        OSError,
        ValueError,
    ) as error:
        parser.error(str(error))

    def solicitar_cierre(_signum: int, _frame: object) -> None:
        node.stop()

    signal.signal(signal.SIGINT, solicitar_cierre)
    signal.signal(signal.SIGTERM, solicitar_cierre)
    logger.info(
        "publicador iniciado: dominio=%s comuna=%s", parsed.dominio, parsed.comuna
    )
    node.run()


if __name__ == "__main__":
    main()
