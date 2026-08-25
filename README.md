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

La capa pub/sub obtiene destinos mediante `MembershipView.vivos()` y consulta
sus tópicos con `MembershipView.topics_de()`. Asi, el trafico de aplicacion solo
se envia a peers confirmados como `alive` sin duplicar las suscripciones fuera
de la vista.

Los TTL y prioridades iniciales de los canales `objetivo` y `subjetivo` se
definen en la sección `pubsub.channels` de `config.example.yaml`. Los reenvíos
pendientes se despachan de mayor a menor prioridad. El grafo simétrico de
adyacencia usado para filtrar destinos está versionado en
`civicmesh/comunas_rm.yaml`.

## Metricas y frontend

Cada peer vuelca sus metricas en `$CIVICMESH_RUNS/<run_id>/metrics/`. En corridas
locales el `run_id` es un identificador propio (p. ej. `local-${USER}-${TS}`);
en el cluster es `$SLURM_JOB_ID`. El directorio de metricas es un simple bloque
de lineas JSON (una por registro). Hay tres tipos de registro distinguidos por
`kind`:

| `kind` | Campos | Para que sirve |
| --- | --- | --- |
| `topic` | `domain`, `topic`, `channel`, `value` | estado y convergencia por topic x canal |
| `state` | `vivos`, `sospechosos`, `muertos`, `total` | experimento de caida / particion |
| `network` | `enviados`, `reenviados`, `descartados_ttl` | sensibilidad a TTL / prioridad |

Todos los registros llevan `run_id`, `ts` (epoch, comparable entre peers) y
`peer`. Ejemplo:

```json
{"kind":"topic","run_id":"local-u-1234","ts":100.0,"peer":"127.0.0.1:7001",
 "domain":"aire","topic":"santiago","channel":"objetivo","value":30.0}
```

### Demo y frontend local

Generar un set de metricas sinteticas y levantar el frontend que lo consume:

```bash
python scripts/demo_metrics.py <dir>            # escribe en <dir>/metrics/
python scripts/frontend.py --metrics <dir>/metrics --port 8080
```

Abrir la UI en `http://127.0.0.1:8080`. La pagina se refresca cada 2 s releyendo
`metrics/`, por lo que refleja corridas en vivo (p. ej. caida de peers). El
frontend muestra tres vistas obligatorias (Seccion 5.4):

- estado por `topic x canal`,
- brecha percepcion-realidad del canal subjetivo,
- convergencia entre peers (dispersion del canal objetivo).

El contrato y las funciones de agregacion viven en `civicmesh/metrics.py`
(`serie_topic`, `brecha_percepcion`, `convergencia`, `ultimo_valor`) y el
resumen consumido por el frontend se arma con `civicmesh.frontend.construir_resumen`.

## Verificacion

```bash
ruff check civicmesh tests scripts
ruff format --check civicmesh tests scripts
python -B -m unittest discover -v
```
