#!/bin/bash
set -euo pipefail

TARGET="${TARGET:-analysis}"
BENCHMARK_ARGS="${BENCHMARK_ARGS:-}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-$(nproc)}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-true}"
export OMP_PLACES="${OMP_PLACES:-cores}"

make "${TARGET}" ARGS="${BENCHMARK_ARGS}"

if [[ -n "${S3_URI:-}" ]]; then
  aws s3 cp . "${S3_URI%/}/" \
    --recursive \
    --exclude "*" \
    --include "*.dat" \
    --include "*.png" \
    --include "job_info.txt"
fi
