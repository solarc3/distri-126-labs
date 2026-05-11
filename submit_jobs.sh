#!/bin/bash
# =============================================================================
# AWS Batch Job Submissions — N-Body Lab1
# =============================================================================
# Requisitos:
#   - AWS CLI configurado con credenciales
#   - Región: us-east-2
#   - Job Queue:  nbody-hpc-queue
#   - Job Def:    distri-jobdef
#   - Bucket S3:  nbody-results-697449782620
# =============================================================================
set -euo pipefail

REGION="us-east-2"
QUEUE="nbody-hpc-queue"
JOBDEF="distri-jobdef"
BUCKET="nbody-results-697449782620"

# Helper: lanza un job y muestra el ID
submit() {
    local name="$1"
    local s3_folder="$2"
    local args="$3"
    local omp_threads="${4:-48}"

    echo "=== Submit: ${name} ==="
    aws batch submit-job \
        --job-name "${name}" \
        --job-queue "${QUEUE}" \
        --job-definition "${JOBDEF}" \
        --container-overrides "$(cat <<EOF
{
    "environment": [
        {"name": "S3_URI",              "value": "s3://${BUCKET}/${s3_folder}/"},
        {"name": "BENCHMARK_ARGS",      "value": "${args}"},
        {"name": "OMP_NUM_THREADS",     "value": "${omp_threads}"},
        {"name": "OMP_PROC_BIND",       "value": "true"},
        {"name": "OMP_PLACES",          "value": "cores"}
    ]
}
EOF
)" \
        --region "${REGION}" \
        --output json | jq -r '.jobId'
    echo
}

echo "==================== FASE 1: N=1000 ===================="

# 1a. N=1000, steps=100, rep=5 — Variante principal
submit \
    "nbody-n1000-accum-static" \
    "n1000-s100-r5-accum-static" \
    "--bodies 1000 --steps 100 --repetitions 5 --extra-repetitions 1 --threads 1,2,4,8,16,24,32,48 --variant-threads 8"

# 1b. N=1000 con más repeticiones para reducir ruido estadístico (opcional)
submit \
    "nbody-n1000-r10-accum-static" \
    "n1000-s100-r10-accum-static" \
    "--bodies 1000 --steps 100 --repetitions 10 --extra-repetitions 3 --threads 1,2,4,8,16,24,32,48 --variant-threads 8"

echo "==================== FASE 2: N=5000 ===================="

submit \
    "nbody-n5000-r3-accum-static" \
    "n5000-s100-r3-accum-static" \
    "--bodies 5000 --steps 100 --repetitions 3 --extra-repetitions 1 --threads 1,2,4,8,16,24,32,48 --variant-threads 8"

submit \
    "nbody-n5000-r5-accum-static" \
    "n5000-s100-r5-accum-static" \
    "--bodies 5000 --steps 100 --repetitions 5 --extra-repetitions 1 --threads 1,2,4,8,16,24,32,48 --variant-threads 8"

echo "==================== FASE 3: N=2000 (interpolacion) ===================="

submit \
    "nbody-n2000-r5-accum-static" \
    "n2000-s100-r5-accum-static" \
    "--bodies 2000 --steps 100 --repetitions 5 --extra-repetitions 1 --threads 1,2,4,8,16,24,32,48 --variant-threads 8"

echo "==================== DONE ===================="
echo "Todos los jobs lanzados. Monitoreá con:"
echo "  aws batch list-jobs --job-queue ${QUEUE} --region ${REGION} --job-status RUNNABLE,RUNNING,STARTING | jq '.jobSummaryList[] | {jobName,status}'"
