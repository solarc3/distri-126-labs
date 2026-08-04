#!/bin/bash
# Barrido GPU-only en el nodo GPU del cluster DIINF (xigpu, A30), pensado para
# correrse DENTRO del contenedor enroot, sobre una allocation ya existente.
#
#   bash run_gpu_diinf.sh
#
# Decisiones:
#  - Solo matriz GPU (--gpu-skip-cpu): la referencia CPU O(N^2) x repetitions es
#    lo que hace que un punto de N=500000 tarde ~10 min extra y no se necesita aca.
#  - Una invocacion del binario POR CADA N: los .dat se abren con truncate, asi que
#    una corrida posterior borraria los datos de la anterior. Separandolas, cada N
#    queda archivado y subido antes de empezar el siguiente.
#  - Sube a S3 despues de cada N: si la allocation se cae a mitad del barrido, todo
#    lo ya medido esta en el bucket.
set -uo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
S3_BASE="${S3_BASE:-s3://nbody-results-697449782620/gpu-diinf}"
AWS_REGION="${AWS_REGION:-us-east-2}"

GPU_N_VALUES="${GPU_N_VALUES:-1000,5000,10000,20000,50000,100000,200000,500000}"
GPU_BLOCK_SIZES="${GPU_BLOCK_SIZES:-64,128,256,512,1024}"
GPU_VARIANTS="${GPU_VARIANTS:-0,1}"
REPETITIONS="${REPETITIONS:-10}"

RUN_TAG="${RUN_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${PROJECT_DIR}/results/gpu-diinf-${RUN_TAG}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-$(nproc)}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-spread}"
export OMP_PLACES="${OMP_PLACES:-cores}"

cd "${PROJECT_DIR}"
mkdir -p "${OUT_DIR}"

have_aws=0
if command -v aws >/dev/null 2>&1; then
  have_aws=1
else
  echo "AVISO: 'aws' no esta disponible aca. Los resultados quedan en ${OUT_DIR};"
  echo "       subelos despues desde el login node o tu laptop."
fi

# $1 = ruta local del archivo. Sube como <S3_BASE>/<nombre-del-archivo>.
upload() {
  local f="$1"
  [[ -s "${f}" ]] || return 0
  [[ "${have_aws}" -eq 1 ]] || return 0
  aws s3 cp "${f}" "${S3_BASE}/$(basename "${f}")" --region "${AWS_REGION}" \
    || echo "AVISO: fallo la subida de $(basename "${f}")"
}

echo "=== Entorno ==="
nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader || \
  { echo "ERROR: nvidia-smi no responde. No estas en un nodo con GPU visible."; exit 1; }

{
  date -u +"%Y-%m-%dT%H:%M:%SZ"
  echo "RUN_TAG: ${RUN_TAG}"
  echo "HOST: $(hostname)"
  echo "SLURM_JOB_ID: ${SLURM_JOB_ID:-n/a}"
  echo "GPU_N_VALUES: ${GPU_N_VALUES}"
  echo "GPU_BLOCK_SIZES: ${GPU_BLOCK_SIZES}"
  echo "GPU_VARIANTS: ${GPU_VARIANTS}"
  echo "REPETITIONS: ${REPETITIONS}"
  echo "MODO: GPU-only (--gpu-skip-cpu)"
  echo "CPU: $(lscpu 2>/dev/null | grep 'Model name' | cut -d: -f2 | xargs || echo N/A)"
  # awk en vez de `head -1`: head cierra el pipe y mata a nvidia-smi con SIGPIPE,
  # que bajo `set -o pipefail` haria fallar la sustitucion.
  echo "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | awk 'NR==1' | xargs || echo N/A)"
  echo "NVCC: $(nvcc --version 2>/dev/null | tail -1 || echo 'NO DISPONIBLE')"
} > "${OUT_DIR}/run_metadata_${RUN_TAG}.txt"
cat "${OUT_DIR}/run_metadata_${RUN_TAG}.txt"

echo
echo "=== Build CUDA ==="
if ! command -v nvcc >/dev/null 2>&1; then
  echo "ERROR: nvcc no esta en PATH; el binario saldria CPU-only y --benchmark-gpu abortaria."
  exit 1
fi
make clean >/dev/null
if ! make -j"$(nproc)" nbody_sim; then
  echo "ERROR: fallo la compilacion."
  exit 1
fi
# Smoke test: un punto minimo de la matriz. Cubre las tres formas de fallar antes
# de gastar la allocation: binario sin NBODY_ENABLE_CUDA_KERNELS (retorna 1 sin
# medir), GPU no visible desde el contenedor (Benchmark.cpp aborta si
# cudaGetDeviceCount() == 0, porque la ruta GPU cae en silencio a CPU), y kernel
# que no lanza.
# No se usa `strings ... | grep -q`: grep -q cierra el pipe al primer match y mata
# a strings con SIGPIPE, que bajo `set -o pipefail` hace fallar la verificacion
# aunque el binario este correcto.
echo "--- smoke test GPU ---"
if ! ./nbody_sim --benchmark-gpu --repetitions 1 --gpu-n-values 256 \
     --gpu-block-sizes 64 --gpu-variants 0 --gpu-skip-cpu; then
  echo "ERROR: el smoke test GPU fallo. El binario no tiene kernels CUDA o no hay GPU visible."
  exit 1
fi
rm -f blockdim_study.dat gpu_benchmark_results.dat
echo "Build OK (kernels CUDA ejecutandose en GPU real)."

upload "${OUT_DIR}/run_metadata_${RUN_TAG}.txt"

failed_n=()
IFS=',' read -r -a n_list <<< "${GPU_N_VALUES}"
for n in "${n_list[@]}"; do
  echo
  echo "=== N=${n} ==="
  start=$(date +%s)
  rm -f blockdim_study.dat gpu_benchmark_results.dat

  ./nbody_sim --benchmark-gpu \
    --repetitions "${REPETITIONS}" \
    --gpu-n-values "${n}" \
    --gpu-block-sizes "${GPU_BLOCK_SIZES}" \
    --gpu-variants "${GPU_VARIANTS}" \
    --gpu-skip-cpu \
    2>&1 | tee "${OUT_DIR}/log_N${n}.txt"
  rc=${PIPESTATUS[0]}

  # Se archiva pase lo que pase: gracias al flush por fila, un N que murio a mitad
  # igual dejo medidos los block sizes que alcanzo a correr.
  if [[ -s blockdim_study.dat ]]; then
    cp -f blockdim_study.dat "${OUT_DIR}/blockdim_study_N${n}.dat"
    upload "${OUT_DIR}/blockdim_study_N${n}.dat"
  fi
  upload "${OUT_DIR}/log_N${n}.txt"

  if [[ ${rc} -ne 0 ]]; then
    echo "AVISO: N=${n} termino con codigo ${rc} (resultados parciales archivados)."
    failed_n+=("${n}")
  fi
  echo "N=${n} tomo $(( $(date +%s) - start ))s"
done

# Matriz consolidada de todos los N que sí produjeron datos, para los graficos.
echo
echo "=== Consolidando ==="
{
  echo -e "# N\tvariant\tblock_size\tkernel_mean_s\tkernel_std_s\tend2end_mean_s\tend2end_std_s"
  grep -h -v '^#' "${OUT_DIR}"/blockdim_study_N*.dat 2>/dev/null | sort -n -k1,1 -k2,2 -k3,3
} > "${OUT_DIR}/blockdim_study.dat"

# `grep -c` imprime el conteo Y sale con 1 cuando no hubo coincidencias, asi que
# un `|| echo 0` concatenaba un segundo "0" y rows quedaba como $'0\n0', con lo
# que el `[[ -gt ]]` de abajo abortaba con "syntax error in expression".
rows=$(grep -c -v '^#' "${OUT_DIR}/blockdim_study.dat" 2>/dev/null) || rows=0
echo "blockdim_study.dat consolidado: ${rows} filas"

if [[ "${rows}" -gt 0 ]]; then
  cp -f "${OUT_DIR}/blockdim_study.dat" ./blockdim_study.dat
  : > gpu_benchmark_results.dat   # sin datos CPU: los paneles de speedup salen vacios
  python3 plot_gpu_benchmarks.py && cp -f gpu_performance_plots.png "${OUT_DIR}/" \
    || echo "AVISO: fallo la generacion de graficos (matplotlib?)"
  upload "${OUT_DIR}/blockdim_study.dat"
  upload "${OUT_DIR}/gpu_performance_plots.png"
fi

echo
echo "=== Listo ==="
echo "Local:  ${OUT_DIR}"
echo "S3:     ${S3_BASE}/"
if [[ ${#failed_n[@]} -gt 0 ]]; then
  echo "N con fallas: ${failed_n[*]}"
  exit 1
fi
