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

echo "=== Registrando dist