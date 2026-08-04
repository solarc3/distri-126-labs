#!/bin/bash
# Usa las 2 A10 del cluster en paralelo: el kernel CUDA del repo no es
# multi-GPU (un solo cudaSetDevice/proceso), asi que el paralelismo se logra
# a nivel de Slurm con un job array de 2 tareas, cada una con --gres=gpu:1
# (Slurm asigna una GPU distinta a cada tarea) corriendo una mitad del
# barrido de N. Mismo patron que run_bodies_sweep.slurm pero para GPU.
#SBATCH --job-name=nbody_gpu_sweep
#SBATCH --partition=GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --array=0-1
#SBATCH --output=job-gpu-%A_%a.out
#SBATCH --error=job-gpu-%A_%a.err

set -euo pipefail

CUDA_MODULE="${CUDA_MODULE:-}"
if [[ -n "${CUDA_MODULE}" ]]; then
  module load "${CUDA_MODULE}"
fi

PROJECT_DIR="${PROJECT_DIR:-${HOME}/distri-l1-126}"
GPU_BLOCK_SIZES="${GPU_BLOCK_SIZES:-64,128,256,512,1024}"
GPU_VARIANTS="${GPU_VARIANTS:-0,1}"
REPETITIONS="${REPETITIONS:-10}"

# Divide el barrido de N en 2 mitades, una por tarea del array / GPU.
N_VALUES_TASK0="${N_VALUES_TASK0:-1000,5000}"
N_VALUES_TASK1="${N_VALUES_TASK1:-10000,20000}"
if [[ "${SLURM_ARRAY_TASK_ID}" == "0" ]]; then
  GPU_N_VALUES="${N_VALUES_TASK0}"
else
  GPU_N_VALUES="${N_VALUES_TASK1}"
fi

WORKDIR="${SLURM_TMPDIR:-/tmp}/nbody_gpu_${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
RESULTS_DIR="${PROJECT_DIR}/results/gpu_sweep_${SLURM_JOB_ID}/task${SLURM_ARRAY_TASK_ID}"

rm -rf "${WORKDIR}"
mkdir -p "${WORKDIR}" "${RESULTS_DIR}"
cp -a "${PROJECT_DIR}/." "${WORKDIR}/"
cd "${WORKDIR}"

echo "=== Tarea ${SLURM_ARRAY_TASK_ID}: N=${GPU_N_VALUES} ==="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true

make clean
make benchmark-gpu ARGS="--repetitions ${REPETITIONS} --gpu-n-values ${GPU_N_VALUES} --gpu-block-sizes ${GPU_BLOCK_SIZES} --gpu-variants ${GPU_VARIANTS}"

cp -f ./*.dat ./*.png "${RESULTS_DIR}/" 2>/dev/null || true
echo "Resultados copiados a ${RESULTS_DIR}"
