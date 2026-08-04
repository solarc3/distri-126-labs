#!/bin/bash
set -euo pipefail

TARGET="${TARGET:-analysis}"
BENCHMARK_ARGS="${BENCHMARK_ARGS:-}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-$(nproc)}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-spread}"
export OMP_PLACES="${OMP_PLACES:-cores}"

# TARGET=benchmark-gpu: los tres ejes de la matriz GPU (N, blockDim.x, variante)
# se pasan como variables de entorno separadas (mas comodo desde AWS Batch
# job parameters que armar BENCHMARK_ARGS a mano) y se agregan a BENCHMARK_ARGS.
if [[ "${TARGET}" == "benchmark-gpu" ]]; then
  [[ -n "${GPU_N_VALUES:-}" ]] && BENCHMARK_ARGS="${BENCHMARK_ARGS} --gpu-n-values ${GPU_N_VALUES}"
  [[ -n "${GPU_BLOCK_SIZES:-}" ]] && BENCHMARK_ARGS="${BENCHMARK_ARGS} --gpu-block-sizes ${GPU_BLOCK_SIZES}"
  [[ -n "${GPU_VARIANTS:-}" ]] && BENCHMARK_ARGS="${BENCHMARK_ARGS} --gpu-variants ${GPU_VARIANTS}"
fi

echo "=== Recompilando con -march=native para CPU target ==="
make clean
make "${TARGET}" ARGS="${BENCHMARK_ARGS}" MARCH_FLAGS="-march=native"

if [ -f "scaling_analysis.dat" ]; then
  echo "=== Generando gráficos de rendimiento ==="
  python3 plot_performance.py || echo "WARNING: plot_performance.py falló"
fi

date -u +"%Y-%m-%dT%H:%M:%SZ" > run_metadata.txt
echo "ARGS: ${BENCHMARK_ARGS:-}" >> run_metadata.txt
echo "OMP_NUM_THREADS: ${OMP_NUM_THREADS:-}" >> run_metadata.txt
echo "TARGET: ${TARGET:-}" >> run_metadata.txt
echo "CPU_INFO: $(lscpu 2>/dev/null | grep 'Model name' | cut -d: -f2 | xargs || echo 'N/A')" >> run_metadata.txt
echo "CPU_FLAGS: $(lscpu 2>/dev/null | grep 'Flags' | cut -d: -f2 | xargs | head -c 500 || echo 'N/A')" >> run_metadata.txt
echo "CPU_CACHE: $(lscpu 2>/dev/null | grep -E 'L1d|L1i|L2|L3|NUMA' | tr '\n' ';' | xargs || echo 'N/A')" >> run_metadata.txt
if command -v numactl >/dev/null 2>&1; then numactl --hardware >> run_metadata.txt 2>/dev/null || true; fi
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "GPU_INFO: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | xargs || echo 'N/A')" >> run_metadata.txt
else
  echo "GPU_INFO: N/A (nvidia-smi no disponible)" >> run_metadata.txt
fi

if [[ -n "${S3_URI:-}" ]]; then
  aws s3 cp . "${S3_URI%/}/" \
    --recursive \
    --exclude "*" \
    --include "*.dat" \
    --include "*.png" \
    --include "*.txt"
fi
