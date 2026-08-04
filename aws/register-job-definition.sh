#!/bin/bash
# =============================================================================
# Registra (o actualiza con una nueva revision) la Job Definition de AWS Batch
# "distri-jobdef" a partir de aws/job-definition.json.
#
# Antes de correr esto la primera vez, editar aws/job-definition.json y
# reemplazar:
#   - containerProperties.image           -> URI real del repo ECR
#   - containerProperties.jobRoleArn      -> rol IAM del task (permisos S3)
#   - containerProperties.executionRoleArn -> rol de ejecucion (ECR + logs)
#
# Cada `aws batch register-job-definition` crea una nueva REVISION de
# "distri-jobdef" (nunca sobreescribe la anterior); los jobs ya corridos
# quedan con la revision con la que se lanzaron.
# =============================================================================
set -euo pipefail

REGION="${REGION:-us-east-2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOB_DEFINITION_FILE="${SCRIPT_DIR}/job-definition.json"

if [[ ! -f "${JOB_DEFINITION_FILE}" ]]; then
  echo "Error: no se encontro ${JOB_DEFINITION_FILE}" >&2
  exit 1
fi

if grep -q "REPLACE_WITH_JOB_ROLE\|REPLACE_WITH_EXECUTION_ROLE" "${JOB_DEFINITION_FILE}"; then
  echo "Error: ${JOB_DEFINITION_FILE} todavia tiene placeholders (REPLACE_WITH_...)." >&2
  echo "Reemplaza jobRoleArn/executionRoleArn por los roles IAM reales antes de registrar." >&2
  exit 1
fi

echo "=== Registrando distri-jobdef en ${REGION} (desde ${JOB_DEFINITION_FILE}) ==="
RESULT=$(aws batch register-job-definition \
  --cli-input-json "file://${JOB_DEFINITION_FILE}" \
  --region "${REGION}" \
  --output json)

echo "${RESULT}" | jq -r '"Registrado: " + .jobDefinitionName + ":" + (.revision | tostring) + " (" + .jobDefinitionArn + ")"'
