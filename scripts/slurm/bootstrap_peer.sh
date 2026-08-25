#!/bin/bash
# Script de inicialización por Peer en Slurm

RUN_DIR=$1
if [ -z "$RUN_DIR" ]; then
    echo "Uso: bootstrap_peer.sh <RUN_DIR>"
    exit 1
fi

# El hostname actual de este nodo Slurm
HOST=$(hostname)
PORT=$((5000 + $SLURM_LOCALID)) # Puerto base + id local

# Registro atómico en el shared FS
echo "$HOST:$PORT" >> "$RUN_DIR/hostfile.txt"

# Leer seeds del hostfile (tomar el primero como seed)
# Esperar unos segundos para que otro peer pueda registrarse
sleep 2
SEED=$(head -n 1 "$RUN_DIR/hostfile.txt")

echo "Iniciando peer en $HOST:$PORT con seed $SEED"

# Ejecutar el proceso peer de Python
python -m civicmesh.node --config "$RUN_DIR/config.yaml" --port $PORT --seeds "$SEED" > "$RUN_DIR/logs/peer_${HOST}_${PORT}.log" 2>&1
