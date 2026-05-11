#!/bin/bash
#SBATCH --job-name=nbody_lab1
#SBATCH --partition=GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=job-%A.out
#SBATCH --error=job-%A.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-${HOME}/distri-l1-126}"
TARGET="${TARGET:-analysis}"
ARGS="${ARGS:-}"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OMP_PROC_BIND=spread
export OMP_PLACES=cores

cd "${PROJECT_DIR}"

make clean
make "${TARGET}" ARGS="${ARGS}"
