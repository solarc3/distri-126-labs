from collections.abc import ItemsView, Iterable, Mapping, Sequence
from typing import Literal, Protocol, TypedDict

# se agregan alias para tener un poquito de typechecking, asi si alguien escribe
# sospechoso o muerto en vez de eso, se rechaza
Estado = Literal["alive", "suspect", "dead", "unknown"]


class DigestState(TypedDict):
    heartbeat: int
    topics: list[str]


class PeerState(DigestState):
    last_seen: float
    estado: Estado


class RandomSource(Protocol):
    def sample(self, population: Sequence[str], k: int) -> list[str]: ...


# los saltos directos a dead son validos si una ronda tarda mas que ambos timeouts
# suspect y dead pueden volver a alive cuando el peer vuelve a escribir directamente
TRANSICIONES_PERMITIDAS: dict[Estado, frozenset[Estado]] = {
    "unknown": frozenset({"alive"}),
    "alive": frozenset({"suspect", "dead"}),
    "suspect": frozenset({"alive", "dead"}),
    "dead": frozenset({"alive"}),
}


class TransicionIlegalError(ValueError):
    """Indica que se intento cambiar un peer entre estados no permitidos."""


class MembershipView:
    transiciones_permitidas = TRANSICIONES_PERMITIDAS

    def __init__(
        self,
        yo: str,
        semillas: Iterable[str],
        t_suspect: float,
        t_dead: float,
    ) -> None:
        self.yo = yo
        self.t_suspect = t_suspect
        self.t_dead = t_dead
        self._topics: list[str] = []
        # el diccionario se va a usar para almacenar los destinos posibles,
        # se debe poder ir actualizando
        # Las seeds entregan los primeros destinos; el resto entra por gossip.
        self._seen: dict[str, PeerState] = {
            semilla: {
                "last_seen": 0.0,
                "heartbeat": 0,
                "topics": [],
                "estado": "unknown",
            }
            for semilla in dict.fromkeys(semillas)
            if semilla != yo
        }

    def _cambiar_estado(self, pid: str, nuevo: Estado) -> None:
        actual = self._seen[pid]["estado"]
        if actual == nuevo:
            return
        if nuevo not in self.transiciones_permitidas[actual]:
            raise TransicionIlegalError(
                f"transicion ilegal para {pid}: {actual} -> {nuevo}"
            )
        self._seen[pid]["estado"] = nuevo

    def contacto_directo(
        self,
        pid: str,
        hb: int,
        topics: list[str],
        now: float,
    ) -> None:
        """Registra un mensaje recibido directamente desde un peer."""
        conocido = self._seen.get(pid)
        if conocido is not None and hb <= conocido["heartbeat"]:
            return

        if conocido is None:
            self._seen[pid] = {
                "last_seen": 0.0,
                "heartbeat": hb,
                "topics": list(topics),
                "estado": "unknown",
            }
        else:
            conocido["heartbeat"] = hb
            conocido["topics"] = list(topics)

        self._cambiar_estado(pid, "alive")
        self._seen[pid]["last_seen"] = now

    def merge_digest(self, digest: Mapping[str, DigestState]) -> None:
        """Incorpora informacion de segunda mano sin confirmar presencia."""
        # recibo info y necesito confirmar
        # se agrega el estado del heartbeat, pq sino se actualiza solo cuando uno
        # lo ve recibe pero quiza otro nodo tiene algo mejor
        # podre tambien propagar el estado? aunq eso implica que existe federacion
        # de info de un nodo a otros, no deberia existir jefatura, todos deben
        # decidir que este muerto
        # TODO: si hay un nodo muerto que en mi lista de vecinos TODOS digan
        # muerto, se elimina(?
        for pid, recibido in digest.items():
            if pid == self.yo:
                continue
            hb = recibido["heartbeat"]
            conocido = self._seen.get(pid)
            if conocido is None:
                self._seen[pid] = {
                    "last_seen": 0.0,
                    "heartbeat": hb,
                    "topics": list(recibido["topics"]),
                    "estado": "unknown",
                }
            elif hb > conocido["heartbeat"]:
                conocido["heartbeat"] = hb
                conocido["topics"] = list(recibido["topics"])

    def set_topics(self, topics: list[str]) -> None:
        """Reemplaza la lista opaca de topics anunciada por el peer local."""
        self._topics = list(topics)

    def topics_de(self, pid: str) -> list[str]:
        """Devuelve una copia de los topics conocidos para un peer."""
        if pid == self.yo:
            return list(self._topics)

        conocido = self._seen.get(pid)
        if conocido is None:
            return []
        return list(conocido["topics"])

    def vivos(self) -> list[str]:
        """Devuelve una instantánea de los peers confirmados como vivos."""
        return [
            peer_id
            for peer_id, estado in self._seen.items()
            if estado["estado"] == "alive"
        ]

    def tick(self, now: float) -> None:
        """Actualiza estados usando la edad de cada contacto directo."""
        # se actualiza edad de los peers mediante last_seen
        # f"{destino[0]}:{destino[1]}"
        # si no esta en last seen se sigue
        # si la edad calculada es < sospechoso se updatea
        for pid, estado_peer in self._seen.items():
            if not estado_peer["last_seen"]:
                continue
            edad = now - estado_peer["last_seen"]
            if edad < self.t_suspect:
                nuevo: Estado = "alive"
            elif edad < self.t_dead:
                nuevo = "suspect"
            else:
                nuevo = "dead"
            self._cambiar_estado(pid, nuevo)

    def digest(self) -> dict[str, DigestState]:
        """Devuelve heartbeat y topics propagados en el mensaje de gossip."""
        return {
            pid: {
                "heartbeat": estado["heartbeat"],
                "topics": list(estado["topics"]),
            }
            for pid, estado in self._seen.items()
        }

    def elegir(self, rng: RandomSource, f: int) -> list[str]:
        """Elige peers no muertos para una ronda de membresia gossip.

        Los peers unknown y suspect siguen siendo candidatos porque gossip debe
        descubrirlos o confirmar su estado. El trafico pub/sub usa ``vivos()``
        y, por lo tanto, solo considera contactos confirmados como alive.
        """
        if f < 0:
            raise ValueError("el fanout no puede ser negativo")
        candidatos = [
            peer_id
            for peer_id, estado in self._seen.items()
            if estado["estado"] != "dead"
        ]
        cantidad = min(f, len(candidatos))
        return rng.sample(candidatos, cantidad)

    def __len__(self) -> int:
        return len(self._seen)

    def items(self) -> ItemsView[str, PeerState]:
        return self._seen.items()
