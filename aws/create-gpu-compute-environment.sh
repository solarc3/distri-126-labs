#!/bin/bash
# =============================================================================
# NO SE EJECUTA AUTOMATICAMENTE. Crea el compute environment + job queue GPU
# que hoy NO existen en la cuenta (697449782620, us-east-2): el compute
# environment actual "distritesting" es CPU-only (c7a/c8i) y esta DISABLED.
#
# AWS no ofrece una instancia con 1 sola H100: la unica familia con H100 es
# "p5", y el tamaño minimo es p5.48xlarge (8x H100 80GB, ~$98/hr on-demand,
# bastante menos en Spot). Para "usar 1 GPU" en Batch, el patron es:
#   - resourceRequirements con GPU=1 en la Job Definition (ya esta asi en
#     aws/job-definition.json)
#   - Batch empaqueta hasta 8 jobs de 1 GPU en el mismo nodo p5.48xlarge
#   - el nodo completo se paga mientras este encendido, sin importar cuantas
#     de sus 8 GPUs esten en uso
#
# Reusa subnets/security group/instance role del compute environment CPU
# existente ("distritesting"), asumiendo que la VPC ya tiene conectividad a
# internet/NAT para pullear la imagen de ECR y subir a S3.
# =============================================================================
set -euo pipefail

REGION="${REGION:-us-east-2}"
CE_NAME="${CE_NAME:-nbody-gpu-h100}"
QUEUE_NAME="${QUEUE_NAME:-nbody-gpu-queue}"
INSTANCE_TYPE="${INSTANCE_TYPE:-p5.48xlarge}"
ALLOCATION_STRATEGY="${ALLOCATION_STRATEGY:-SPOT_CAPACITY_OPTIMIZED}"  # o BEST_FIT_PROGRESSIVE para on-demand
TYPE="${TYPE:-SPOT}"  # o EC2 para on-demand (mas caro, mas disponible)
MAX_VCPUS="${MAX_VCPUS:-192}"  # 1x p5.48xlarge (192 vCPU); subir si se quiere mas de un nodo a la vez

SUBNETS="subnet-091d0dcf23e7a59ad,subnet-059de551de587c028,subnet-06d2ccfa2a793d7c2"
SECURITY_GROUPS="sg-045f0d751a1a32917"
INSTANCE_ROLE="arn:aws:iam::697449782620:instance-profile/ecsInstanceRole"

echo "=== 1/2: creando compute environment '${CE_NAME}' (${TYPE}, ${INSTANCE_TYPE}) ==="
aws batch create-compute-environment \
    --compute-environment-name "${CE_NAME}" \
    --type MANAGED \
    --state ENABLED \
    --compute-resources "type=${TYPE},allocationStrategy=${ALLOCATION_STRATEGY},minvCpus=0,maxvCpus=${MAX_VCPUS},desiredvCpus=0,instanceTypes=${INSTANCE_TYPE},subnets=${SUBNETS},securityGroupIds=${SECURITY_GROUPS},instanceRole=${INSTANCE_ROLE}" \
    --region "${REGION}"

echo "=== esperando a que el compute environment quede VALID ==="
aws batch wait compute-environment-valid --compute-environments "${CE_NAME}" --region "${REGION}" || true

echo "=== 2/2: creando job queue '${QUEUE_NAME}' ==="
aws batch create-job-queue \
    --job-queue-name "${QUEUE_NAME}" \
    --state ENABLED \
    --priority 1 \
    --compute-environment-order "order=1,computeEnvironment=${CE_NAME}" \
    --region "${REGION}"

echo "=== DONE ==="
echo "Antes de correr un job de verdad: registra la job definition"
echo "  ./aws/register-job-definition.sh"
echo "y despues lanza con:"
echo "  QUEUE=${QUEUE_NAME} ./aws/submit_gpu_jobs.sh"
echo
echo "IMPORTANTE: el compute environment queda ENABLED con minvCpus=0, asi que"
echo "no cobra nada hasta que se lance un job GPU; pero mientras un job este"
echo "corriendo, se factura el nodo p5.48xlarge COMPLETO (8x H100), no una GPU"
echo "aislada. Para apagarlo del todo:"
echo "  aws batch update-job-queue --job-queue ${QUEUE_NAME} --state DISABLED --region ${REGION}"
echo "  aws batch update-compute-environment --compute-environment ${CE_NAME} --state DISABLED --region ${REGION}"
