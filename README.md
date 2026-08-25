# CivicMesh (Laboratorio 3)

Un framework P2P de Publish/Subscribe para monitoreo ciudadano distribuido basado en Gossip.

## Requisitos
- Python >= 3.10
- Docker y Docker Compose
- Slurm (para despliegue en clúster)

## Roles del Equipo
| Nombre | Rol | Responsabilidad |
|--------|-----|-----------------|
|        | Líder de Capa de Red / Gossip | Membresía, descubrimiento, tolerancia a fallos |
|        | Líder de Capa Pub/Sub | Tópicos, suscripciones, `should_forward`, fanout |
|        | Líder de Datos | Ingesta Dominio B, generadores Poisson, percepción ciudadana |
|        | Líder de Analítica | Métricas, convergencia, divergencia, frontend UI |
| Fabian | Líder de CI/CD, Git y Agentes | Pipeline CI, Docker Compose, scripts Slurm, Agentes |

## Instalación
```bash
# Entorno virtual recomendado
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest ruff
```

## Pruebas y Linter
Este repositorio utiliza `pytest` para pruebas y `ruff` para linting y formateo.
```bash
make lint
make test
```

## Ejecución Local (Docker Compose)
Para levantar la malla con perfiles específicos, usar:
```bash
# Dominio A (Delitos)
make compose-delitos

# Dominio B (Aire)
make compose-aire
```
O directamente con Docker Compose:
`docker compose --profile delitos up --build`

## Ejecución en Clúster DIINF (Slurm)
Los logs de corrida y métricas se guardarán bajo la convención `$CIVICMESH_RUNS/<run_id>/`.
```bash
make run-cluster
# o
sbatch scripts/slurm/run_cluster.slurm
```

## Interfaz de Analítica (Frontend)
El frontend estará disponible en el puerto `8080`.
Si corres en Slurm, debes hacer un túnel SSH hacia el host GPU que corre el frontend:
```bash
ssh -L 8080:localhost:8080 usuario@cluster -J usuario@gw
```

## Agentes de IA
Este repositorio cuenta con 3 agentes:
1. **Documentador (`agent_docs.yml`)**: Semanal, verifica estado de docs.
2. **Revisor de Bugs (`agent_bugs.yml`)**: Diario, verifica correctitud de código Python, gossip y pub/sub.
3. **Revisor de MR (`agent_pr.yml`)**: En cada PR, clasifica impacto, corre tras pasar CI verde. Nunca hace merge.
