#!/bin/bash
#SBATCH --job-name=nbody_gpu
#SBATCH --partition=GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
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

nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true

make clean
make benchmark-gpu ARGS="--repetitions ${REPETITIONS} --gpu-n-values ${GPU_N_VALUES} --gpu-block-sizes ${GPU_BLOCK_SIZES} --gpu-variants ${GPU_VARIANTS}"

RESULTS_DIR="${PROJECT_DIR}/results/gpu_${SLURM_JOB_ID}"
mkdir -p "${RESULTS_DIR}"
cp -f ./*.dat ./*.png "${RESULTS_DIR}/" 2>/dev/null || true
echo "Resultados copiados a ${RESULTS_DIR}"
