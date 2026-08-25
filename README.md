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

## Dominios: generadores, datos de aire y publicadores

`civicmesh/domains/` implementa los dos dominios de la Sección 4 sobre el
mismo framework (membresía + pub/sub) de arriba, sin tocarlo:

| Módulo | Responsabilidad |
| --- | --- |
| `percepcion.py` | Matemática común del canal subjetivo: `MemoriaEMA` (EMA), `AgregadorRumores` (`Q`/`\hat P^gossip`), `sigmoide`, `clip`. |
| `rng.py` | RNG determinista: `rng_compuesto(seed, *partes)` (seed + hash estable, no depende de `PYTHONHASHSEED`) y `poisson(rng, lam)`. |
| `config.py` | Carga y valida `generadores.yaml` (tasas `lambda_{c,k}`, `beta`/`gamma`/`delta`/`alpha`/`sigma_eps`, método de extrapolación). |
| `domain_a.py` | Dominio A (delitos): `DomainAPublisher` genera `Poisson(lambda_{c,k} dt)` por tipo, publica el canal objetivo y calcula `P_c(t)` (Ec. 1-3) para el subjetivo. |
| `coords.py` | Coordenadas aproximadas por comuna y distancia Haversine, solo para el Dominio B. |
| `air_quality_cache.py` | Carga `data/air_quality/<comuna>.json` (series reales cacheadas); rellena huecos hacia adelante. |
| `extrapolacion.py` | `vecino_mas_cercano` / `promedio_vecinos` / `idw` (Sección 4.2) y `ProveedorAire`, que da `v_c(t)` real o extrapolado. |
| `replay.py` | `ReplayAire`: avanza `v_c(t)` instante a instante para una comuna (con o sin loop). |
| `domain_b.py` | Dominio B (aire): `DomainBPublisher` publica la muestra real/extrapolada como canal objetivo y la percepción con memoria de pico (Ec. 4-5) como subjetivo. |
| `publisher_main.py` | CLI: arma un publicador como peer completo (gossip + pub/sub + el dominio elegido) y lo corre. |

Ambos publicadores comparten el mismo contrato con `should_forward`/TTL/
prioridad de la capa Pub/Sub: se suscriben a su propia comuna, publican con
`PubSub.publish(...)` y escuchan sus propios rumores (`Q`) vía
`PubSub.agregar_callback(...)`, filtrando los mensajes cuyo `origin` sea su
propio peer ID para no auto-alimentarse.

### Configuración (Sección 4.3)

`generadores.example.yaml` fija, en un archivo versionado, `seed`, las tasas
`lambda_{c,k}` del Dominio A (semillas ilustrativas, no cifras oficiales) y
los parámetros de percepción de ambos dominios. `publicadores.example.yaml`
define la red (bind/advertise/seeds) para procesos publicador, separada de
`config.example.yaml` para no acoplar peers CPU y publicadores.

### Datos reales de aire (Apéndice A)

```bash
python scripts/fetch_open_meteo.py --start-date 2025-06-01 --end-date 2025-06-03
```

Descarga PM2.5/PM10 horario desde Open-Meteo (sin API key) y cachea un JSON
por comuna en `data/air_quality/`. Por defecto usa 6 comunas ancla con
buena cobertura espacial del Gran Santiago (`santiago`, `las_condes`,
`maipu`, `la_florida`, `penalolen`, `pudahuel`); el resto de las comunas de
`generadores.example.yaml` se extrapola en tiempo de ejecución (método
configurable: vecino más cercano, promedio de vecinos o IDW) y **no**
requiere su propia estación. El repo versiona el cache ya descargado para
que el experimento sea reproducible sin depender de la red el día de la
defensa; para regenerarlo o ampliar la cobertura, correr el script de nuevo.

### Correr un publicador

```bash
python -m civicmesh.domains.publisher_main \
  --config publicadores.example.yaml --peer publicador-delitos-1 \
  --dominio delitos --comuna santiago

python -m civicmesh.domains.publisher_main \
  --config publicadores.example.yaml --peer publicador-aire-1 \
  --dominio aire --comuna las_condes
```

El publicador se une a la malla como un peer más (usa como *seed* un peer
CPU ya definido en `config.example.yaml`), por lo que hereda las mismas
políticas de TTL/prioridad/fanout documentadas arriba. En el clúster DIINF
corre en un host GPU usando solo la CPU del host (Sección 5.1); no usa CUDA.

## Verificacion

```bash
ruff check civicmesh tests scripts
ruff format --check civicmesh tests scripts
python -B -m unittest discover -v
```
