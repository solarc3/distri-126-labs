#!/bin/bash
set -euo pipefail

TARGET="${TARGET:-analysis}"
BENCHMARK_ARGS="${BENCHMARK_ARGS:-}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-$(nproc)}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-true}"
export OMP_PLACES="${OMP_PLACES:-cores}"

make "${TARGET}" ARGS="${BENCHMARK_ARGS}"

if [ -f "scaling_analysis.dat" ]; then
  echo "=== Generando gráficos de rendimiento ==="
  python3 plot_performance.py || echo "WARNING: plot_performance.py falló"
fi

date -u +"%Y-%m-%dT%H:%M:%SZ" > run_metadata.txt
echo "ARGS: ${BENCHMARK_ARGS:-}" >> run_metadata.txt
echo "OMP_NUM_THREADS: ${OMP_NUM_THREADS:-}" >> run_metadata.txt
echo "TARGET: ${TARGET:-}" >> run_metadata.txt

if [[ -n "${S3_URI:-}" ]]; then
  aws s3 cp . "${S3_URI%/}/" \
    --recursive \
    --exclude "*" \
    --include "*.dat" \
    --include "*.png" \
    --include "*.txt"
fi
