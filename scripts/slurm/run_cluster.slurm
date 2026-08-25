#!/bin/bash
#SBATCH --job-name=civicmesh
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=lucatiel # Reemplazar con la partición real del clúster usando 'sinfo'
#SBATCH --output=logs/civicmesh_%j.out
#SBATCH --error=logs/civicmesh_%j.err

# Directorio base en el filesystem compartido (HOME suele estar montado)
export CIVICMESH_RUNS="$HOME/civicmesh_runs"
export RUN_DIR="$CIVICMESH_RUNS/$SLURM_JOB_ID"

echo "=== Iniciando CivicMesh RUN $SLURM_JOB_ID ==="
echo "Directorio de la corrida: $RUN_DIR"

# 1. Crear el entorno compartido
mkdir -p "$RUN_DIR/metrics"
mkdir -p "$RUN_DIR/logs"
touch "$RUN_DIR/hostfile.txt"

# Copiar config actual
cp config.example.yaml "$RUN_DIR/config.yaml"
# Copiar dataset de aire si existe
# cp -r data/ "$RUN_DIR/" 2>/dev/null || true

# Separar nodos: 2 para CPU (Peers) y 2 para GPU (Publisher/Frontend usando solo CPU)
NODES=($(scontrol show hostnames $SLURM_JOB_NODELIST))
CPU_NODES="${NODES[0]},${NODES[1]}"
GPU_NODES="${NODES[2]},${NODES[3]}"

echo "Nodos CPU (Peers): $CPU_NODES"
echo "Nodos GPU (Publishers/UI): $GPU_NODES"

# 2. Levantar Peers en los nodos CPU
echo "=== Lanzando Peers en background ==="
srun --nodelist="$CPU_NODES" --ntasks=2 bash scripts/slurm/bootstrap_peer.sh "$RUN_DIR" &
PEERS_PID=$!

# Esperar a que los peers se registren en el hostfile
echo "Esperando registro de peers en hostfile.txt..."
sleep 10
cat "$RUN_DIR/hostfile.txt"

# 3. Levantar Publisher y Frontend en los nodos GPU (sin usar CUDA, solo CPU del host)
echo "=== Lanzando Publishers y Frontend ==="
srun --nodelist="${NODES[2]}" --ntasks=1 python -m civicmesh.node --config "$RUN_DIR/config.yaml" --role publisher --domain aire --seeds_file "$RUN_DIR/hostfile.txt" > "$RUN_DIR/logs/publisher.log" 2>&1 &

srun --nodelist="${NODES[3]}" --ntasks=1 python -m civicmesh.node --role frontend > "$RUN_DIR/logs/frontend.log" 2>&1 &

# 4. Esperar finalización o timeout (ej. 60 segundos)
echo "El clúster está corriendo. Las métricas se guardarán en $RUN_DIR/metrics/"
sleep 60

echo "=== Finalizando simulación ==="
scancel $SLURM_JOB_ID
