"""Transporte UDP compartido por los componentes de un peer."""

import logging
import socket
from collections.abc import Callable
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import TypeAlias

from civicmesh.protocol import (
    PeerId,
    ProtocolError,
    Sobre,
    TipoMensaje,
    codificar_sobre,
    decodificar_sobre,
)

logger = logging.getLogger(__name__)

Handler: TypeAlias = Callable[[Sobre], None]
Endpoint: TypeAlias = tuple[str, int]


class EndpointError(ValueError):
    """Indica que un peer ID no representa un endpoint UDP valido."""


def parse_endpoint(peer_id: PeerId) -> Endpoint:
    """Convierte un peer ID host:puerto en un endpoint UDP."""
    try:
        host, puerto_texto = peer_id.rsplit(":", maxsplit=1)
    except ValueError as error:
        raise EndpointError("se esperaba un endpoint host:puerto") from error

    if not host:
        raise EndpointError("el host no puede estar vacio")

    try:
        puerto = int(puerto_texto)
    except ValueError as error:
        raise EndpointError("el puerto debe ser un entero") from error

    if not 1 <= puerto <= 65535:
        raise EndpointError("el puerto debe estar entre 1 y 65535")

    return host, puerto


def resolve_endpoints(peer_id: PeerId) -> frozenset[Endpoint]:
    """Resuelve un peer ID a sus endpoints UDP IPv4."""
    host, puerto = parse_endpoint(peer_id)

    try:
        resultados = socket.getaddrinfo(
            host,
            puerto,
            family=socket.AF_INET,
            type=socket.SOCK_DGRAM,
        )
    except socket.gaierror as error:
        raise EndpointError(f"no se pudo resolver el host {host}") from error

    endpoints: set[Endpoint] = set()
    for _family, _type, _proto, _canonname, sockaddr in resultados:
        endpoints.add((sockaddr[0], sockaddr[1]))

    if not endpoints:
        raise EndpointError(f"el host {host} no tiene direcciones IPv4")

    return frozenset(endpoints)


class Transport:
    """Posee el socket UDP y distribuye sobres a handlers registrados."""

    def __init__(self, peer_id: PeerId, bind: Endpoint) -> None:
        _host_anunciado, puerto_anunciado = parse_endpoint(peer_id)

        self.peer_id = peer_id
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._handlers: dict[TipoMensaje, Handler] = {}
        self._inbox: Queue[Sobre] = Queue(maxsize=1024)
        self.blocked_peers: set[PeerId] = set()
        self._endpoint_cache: dict[PeerId, frozenset[Endpoint]] = {}

        try:
            self._sock.bind(bind)
        except OSError:
            self._sock.close()
            raise

        puerto_enlazado = self._sock.getsockname()[1]
        if puerto_enlazado != puerto_anunciado:
            self._sock.close()
            raise ValueError("el puerto anunciado debe coincidir con el puerto de bind")

        self._sock.settimeout(0.2)
        self._stop_event = Event()
        self._receiver_thread: Thread | None = None

    def close(self) -> None:
        self._stop_event.set()
        self._sock.close()

        thread = self._receiver_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def send(self, peer_id: PeerId, sobre: Sobre) -> None:
        data = codificar_sobre(sobre)
        if sobre["from"] != self.peer_id:
            raise ValueError("el remitente del sobre no coincide con el transporte")
        if peer_id in self.blocked_peers:
            return

        destino = parse_endpoint(peer_id)
        self._sock.sendto(data, destino)

    def register_handler(
        self,
        tipo: TipoMensaje,
        handler: Handler,
    ) -> None:
        if tipo in self._handlers:
            raise ValueError(f"ya existe un handler para {tipo}")

        self._handlers[tipo] = handler

    def dispatch_pending(self, max_messages: int = 100) -> int:
        if max_messages < 0:
            raise ValueError("max_messages no puede ser negativo")

        procesados = 0
        while procesados < max_messages:
            try:
                sobre = self._inbox.get_nowait()
            except Empty:
                break

            handler = self._handlers.get(sobre["tipo"])
            if handler is None:
                logger.warning(
                    "mensaje descartado: no hay handler para %s",
                    sobre["tipo"],
                )
            else:
                try:
                    handler(sobre)
                except Exception:
                    logger.exception(
                        "fallo el handler: tipo=%s remitente=%s",
                        sobre["tipo"],
                        sobre["from"],
                    )

            procesados += 1

        return procesados

    def _receive_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                data, addr = self._sock.recvfrom(65535)
            except TimeoutError:
                continue
            except OSError:
                if self._stop_event.is_set():
                    return

                logger.exception("fallo la recepcion UDP")
                return

            try:
                sobre = decodificar_sobre(data)
            except ProtocolError as error:
                logger.warning("datagrama descartado: %s", error)
                continue

            if sobre["from"] in self.blocked_peers:
                continue

            observado: Endpoint = (addr[0], addr[1])
            try:
                esperados = self._endpoint_cache.get(sobre["from"])
                if esperados is None:
                    esperados = resolve_endpoints(sobre["from"])
                    self._endpoint_cache[sobre["from"]] = esperados
            except EndpointError as error:
                logger.warning("remitente descartado: %s", error)
                continue

            if observado not in esperados:
                logger.warning(
                    "remitente inconsistente: declarado=%s observado=%s",
                    sobre["from"],
                    observado,
                )
                continue

            try:
                self._inbox.put_nowait(sobre)
            except Full:
                logger.warning("datagrama descartado: la cola esta llena")

    def start(self) -> None:
        if self._stop_event.is_set():
            raise RuntimeError("no se puede reiniciar un transporte cerrado")

        if self._receiver_thread is not None:
            raise RuntimeError("el transporte ya fue iniciado")

        self._receiver_thread = Thread(
            target=self._receive_loop,
            name=f"transport-recv-{self.peer_id}",
            daemon=True,
        )
        self._receiver_thread.start()
