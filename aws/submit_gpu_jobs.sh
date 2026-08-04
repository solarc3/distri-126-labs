#!/bin/bash
# =============================================================================
# AWS Batch — Benchmarks GPU (N-Body Lab2, seccion 8.2)
# =============================================================================
# Los tres ejes de la matriz (N, blockDim.x, variante) y el resto de opciones
# son PARAMETROS de la Job Definition "distri-jobdef" (ver aws/job-definition.json,
# bloque "parameters"), no valores hardcodeados en este script. Para correr con
# otro N basta con pasar --parameters distinto, sin editar nada del repo:
#
#   aws batch submit-job \
#       --job-name nbody-gpu-h100-n5000 \
#       --job-queue nbody-gpu-queue \
#       --job-definition distri-jobdef \
#       --region us-east-2 \
#       --parameters target=benchmark-gpu,repetitions=10,gpu_n_values="1000\,5000\,10000\,20000",s3_uri="s3://nbody-results-697449782620/gpu-h100-n5000/"
#
# (las comas dentro de un valor de --parameters se escapan con "\,": la CLI
# separa por comas los distintos key=value).
#
# Requisitos:
#   - AWS CLI configurado con credenciales (aws sts get-caller-identity debe
#     responder OK)
#   - Compute environment con instancias GPU (p5.* para H100) HABILITADO y
#     agregado a una Job Queue GPU — no existe todavia en la cuenta; ver
#     create-gpu-compute-environment.sh
#   - Job Def "distri-jobdef" registrada desde aws/job-definition.json
#     (aws/register-job-definition.sh)
#   - Imagen ECR con los kernels CUDA compilados (Dockerfile del repo)
# =============================================================================
set -euo pipefail

REGION="${REGION:-us-east-2}"
QUEUE="${QUEUE:-nbody-gpu-queue}"
JOBDEF="${JOBDEF:-distri-jobdef}"
BUCKET="${BUCKET:-nbody-results-697449782620}"

# Helper: lanza un job de benchmark GPU. Cualquier parametro de la Job
# Definition puede sobreescribirse acá (target, gpu_n_values, gpu_block_sizes,
# gpu_variants, repetitions, s3_uri, ...); los que no se pasan usan el default
# definido en aws/job-definition.json.
#   name          nombre del job en AWS Batch
#   s3_folder     subcarpeta en el bucket de resultados
#   gpu_n_values  lista de N separada por coma (sin escapar; se escapa acá)
#   extra_params  parametros adicionales "key=value,key=value" (opcional)
submit() {
    local name="$1"
    local s3_folder="$2"
    local gpu_n_values="$3"
    local extra_params="${4:-}"
    local escaped_n_values="${gpu_n_values//,/\\,}"

    local params="target=benchmark-gpu,gpu_n_values=${escaped_n_values},s3_uri=s3://${BUCKET}/${s3_folder}/"
    [[ -n "${extra_params}" ]] && params="${params},${extra_params}"

    echo "=== Submit: ${name} (N=${gpu_n_values}) ==="
    aws batch submit-job \
        --job-name "${name}" \
        --job-queue "${QUEUE}" \
        --job-definition "${JOBDEF}" \
        --parameters "${params}" \
        --region "${REGION}" \
        --output json | jq -r '.jobId'
    echo
}

echo "==================== Benchmark GPU: matriz N x variante x blockDim.x (1x H100) ===================="

# N mas grande que en CPU: una sola H100 (80GB) soporta N mucho mayor que el
# barrido original ({256,512,1024,2000}); 20000 sigue siendo liviano en
# memoria para O(N^2) pero ya muestra bien el crossover GPU vs CPU.
submit \
    "nbody-gpu-h100-sweep" \
    "gpu-h100-sweep" \
    "1000,5000,10000,20000" \
    "repetitions=10"

echo "==================== DONE ===================="
echo "Monitoreá con:"
echo "  aws batch list-jobs --job-queue ${QUEUE} --region ${REGION} --job-status RUNNABLE,RUNNING,STARTING | jq '.jobSummaryList[] | {jobName,status}'"
