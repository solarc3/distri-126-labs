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
CONTAINER_IMAGE="${CONTAINER_IMAGE:-docker.io#ubuntu:22.04}"
TARGET="${TARGET:-analysis}"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OMP_PROC_BIND=true
export OMP_PLACES=cores

srun \
  --container-image="${CONTAINER_IMAGE}" \
  --container-mounts="${HOME}:${HOME}" \
  --container-workdir="${PROJECT_DIR}" \
  sh -c "apt-get update &&
         apt-get install -y --no-install-recommends build-essential make python3 python3-numpy python3-matplotlib ca-certificates &&
         make clean &&
         make ${TARGET}"
