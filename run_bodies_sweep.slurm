#!/bin/bash
#SBATCH --job-name=nbody_sweep
#SBATCH --partition=GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --array=0-3
#SBATCH --output=job-%A_%a.out
#SBATCH --error=job-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-${HOME}/distri-l1-126}"
BODIES_LIST="${BODIES_LIST:-500 1000 2000 4000}"
STEPS="${STEPS:-500}"
REPETITIONS="${REPETITIONS:-10}"
EXTRA_REPETITIONS="${EXTRA_REPETITIONS:-3}"
THREADS="${THREADS:-1,2,4,8,16}"
VARIANT_THREADS="${VARIANT_THREADS:-4}"

read -r -a BODIES_VALUES <<< "${BODIES_LIST}"
if (( SLURM_ARRAY_TASK_ID >= ${#BODIES_VALUES[@]} )); then
  echo "No hay valor de N para SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID}" >&2
  exit 1
fi
N="${BODIES_VALUES[${SLURM_ARRAY_TASK_ID}]}"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OMP_PROC_BIND=spread
export OMP_PLACES=cores

WORKDIR="${SLURM_TMPDIR:-/tmp}/nbody_${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
RESULTS_DIR="${PROJECT_DIR}/results/N${N}"

rm -rf "${WORKDIR}"
mkdir -p "${WORKDIR}" "${RESULTS_DIR}"
cp -a "${PROJECT_DIR}/." "${WORKDIR}/"

cd "${WORKDIR}"
make clean
make analysis ARGS="--bodies ${N} --steps ${STEPS} --repetitions ${REPETITIONS} --extra-repetitions ${EXTRA_REPETITIONS} --threads ${THREADS} --variant-threads ${VARIANT_THREADS}"

cp -f ./*.dat ./*.png "${RESULTS_DIR}/"
