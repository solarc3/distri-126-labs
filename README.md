# CivicMesh

Infraestructura P2P de membresia gossip y transporte compartido para la capa
publish/subscribe del Laboratorio 3.

## Ejecucion local

El archivo `config.example.yaml` define tres peers. Ejecutar cada uno en una
terminal distinta:

```bash
python -m civicmesh.node --config config.example.yaml --peer peer-1
python -m civicmesh.node --config config.example.yaml --peer peer-2
python -m civicmesh.node --config config.example.yaml --peer peer-3
```

## Politica de fanout y estados

El fanout de membresia y el fanout de pub/sub son decisiones separadas:

| Estado | Gossip | Pub/sub |
| --- | --- | --- |
| `unknown` | candidato | excluido |
| `alive` | candidato | candidato |
| `suspect` | candidato | excluido |
| `dead` | excluido | excluido |

Gossip elige uniformemente hasta `fanout` peers entre los estados `unknown`,
`alive` y `suspect`. Mantener `unknown` permite el bootstrap y mantener
`suspect` permite confirmar si un peer sigue disponible. Los peers `dead` se
excluyen para no gastar rondas en endpoints cuyo timeout ya vencio; un proceso
que reinicia puede volver a `alive` al contactar directamente a un peer activo.

La futura capa pub/sub debe obtener destinos mediante `MembershipView.vivos()`.
Asi, el trafico de aplicacion solo se envia a peers confirmados como `alive` y
no depende de la estructura interna `PeerState`.

## Verificacion

```bash
ruff check civicmesh tests
ruff format --check civicmesh tests
python -B -m unittest discover -v
```
