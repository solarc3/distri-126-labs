#!/bin/bash
#SBATCH --job-name=nbody_gpu
#SBATCH --partition=GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --gres=gpu:1
#SBATCH --time=04:00:00
#SBATCH --output=job-gpu-%A.out
#SBATCH --error=job-gpu-%A.err

set -euo pipefail

# Ajusta el nombre del module de CUDA al que exista en DIINF (ver `module avail cuda`).
CUDA_MODULE="${CUDA_MODULE:-}"
if [[ -n "${CUDA_MODULE}" ]]; then
  module load "${CUDA_MODULE}"
fi

PROJECT_DIR="${PROJECT_DIR:-${HOME}/distri-l1-126}"
GPU_N_VALUES="${GPU_N_VALUES:-1000,5000,10000,20000}"
GPU_BLOCK_SIZES="${GPU_BLOCK_SIZES:-64,128,256,512,1024}"
GPU_VARIANTS="${GPU_VARIANTS:-0,1}"
REPETITIONS="${REPETITIONS:-10}"

cd "${PROJECT_DIR}"

RESULTS_DIR="${PROJECT_DIR}/results/gpu_${SLURM_JOB_ID:-local}"
mkdir -p "${RESULTS_DIR}"

# Rescate de resultados: el benchmark escribe los .dat fila por fila (flush por
# punto de la matriz), asi que si el job muere por timeout de Slurm o por un error
# de CUDA lo ya medido sigue en disco. Este trap lo copia a results/ y lo sube a S3
# igual, en vez de perderlo porque `make` retorno != 0 con `set -e`.
collect_results() {
  local status=$?
  cp -f ./*.dat ./*.png ./run_metadata.txt "${RESULTS_DIR}/" 2>/dev/null || true
  echo "Resultados (parciales o completos) en ${RESULTS_DIR}"
  if [[ -n "${S3_URI:-}" ]]; then
    if command -v aws >/dev/null 2>&1; then
      aws s3 cp "${RESULTS_DIR}/" "${S3_URI%/}/" --recursive \
        || echo "WARNING: fallo la subida a S3 (revisa credenciales/salida a internet del nodo)"
    else
      echo "WARNING: S3_URI definido pero 'aws' no esta en el contenedor; sube desde el login node."
    fi
  fi
  exit "${status}"
}
trap collect_results EXIT

{
  date -u +"%Y-%m-%dT%H:%M:%SZ"
  echo "JOB: ${SLURM_JOB_ID:-local}  NODE: $(hostname)"
  echo "GPU_N_VALUES: ${GPU_N_VALUES}"
  echo "GPU_BLOCK_SIZES: ${GPU_BLOCK_SIZES}"
  echo "GPU_VARIANTS: ${GPU_VARIANTS}"
  echo "REPETITIONS: ${REPETITIONS}"
  echo "OMP_NUM_THREADS: ${OMP_NUM_THREADS:-unset}"
  echo "CPU: $(lscpu 2>/dev/null | grep 'Model name' | cut -d: -f2 | xargs || echo N/A)"
  echo "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | xargs || echo N/A)"
} > run_metadata.txt
cat run_metadata.txt

make clean
make benchmark-gpu ARGS="--repetitions ${REPETITIONS} --gpu-n-values ${GPU_N_VALUES} --gpu-block-sizes ${GPU_BLOCK_SIZES} --gpu-variants ${GPU_VARIANTS}"
