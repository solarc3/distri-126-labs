from collections.abc import Iterable, ItemsView, Mapping, Sequence
from typing import Literal, Protocol, TypedDict

# se agregan alias para tener un poquito de typechecking, asi si alguien escribe
# sospechoso o muerto en vez de eso, se rechaza
Estado = Literal["alive", "suspect", "dead", "unknown"]


class PeerState(TypedDict):
    last_seen: float
    heartbeat: int
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
        # el diccionario se va a usar para almacenar los destinos posibles,
        # se debe poder ir actualizando
        # Las seeds entregan los primeros destinos; el resto entra por gossip.
        self._seen: dict[str, PeerState] = {
            semilla: {"last_seen": 0.0, "heartbeat": 0, "estado": "unknown"}
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

    def contacto_directo(self, pid: str, hb: int, now: float) -> None:
        """Registra un mensaje recibido directamente desde un peer."""
        if pid not in self._seen:
            self._seen[pid] = {
                "last_seen": 0.0,
                "heartbeat": hb,
                "estado": "unknown",
            }

        self._cambiar_estado(pid, "alive")
        self._seen[pid]["last_seen"] = now
        self._seen[pid]["heartbeat"] = hb

    def merge_digest(self, digest: Mapping[str, int]) -> None:
        """Incorpora informacion de segunda mano sin confirmar presencia."""
        # recibo info y necesito confirmar
        # se agrega el estado del heartbeat, pq sino se actualiza solo cuando uno
        # lo ve recibe pero quiza otro nodo tiene algo mejor
        # podre tambien propagar el estado? aunq eso implica que existe federacion
        # de info de un nodo a otros, no deberia existir jefatura, todos deben
        # decidir que este muerto
        # TODO: si hay un nodo muerto que en mi lista de vecinos TODOS digan
        # muerto, se elimina(?
        for pid, hb in digest.items():
            if pid == self.yo:
                continue
            if pid not in self._seen:
                self._seen[pid] = {
                    "last_seen": 0.0,
                    "heartbeat": hb,
                    "estado": "unknown",
                }
            elif hb > self._seen[pid]["heartbeat"]:
                self._seen[pid]["heartbeat"] = hb

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

    def digest(self) -> dict[str, int]:
        """Devuelve los heartbeats que se propagan en el mensaje de gossip."""
        return {pid: estado["heartbeat"] for pid, estado in self._seen.items()}

    def elegir(self, rng: RandomSource, f: int) -> list[str]:
        """Elige hasta f destinos distintos de toda la vista local."""
        if f < 0:
            raise ValueError("el fanout no puede ser negativo")
        cantidad = min(f, len(self._seen))
        return rng.sample(list(self._seen), cantidad)

    def __len__(self) -> int:
        return len(self._seen)

    def items(self) -> ItemsView[str, PeerState]:
        return self._seen.items()
