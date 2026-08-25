---
engine:
  id: copilot
  model: gpt-4o
on:
  schedule: weekly on sunday
permissions:
  contents: read
  issues: read
  pull-requests: read
safe-outputs:
  create-issue:
    labels: [documentation, agent]
  create-pull-request:
    title-prefix: "[agent: auto-fix] "
---
## Tarea del Agente
Revisa el estado de la documentación en el repositorio, específicamente el `README.md`, el `CHANGELOG.md` y los docstrings en los archivos de Python (`civicmesh/`).

## Reglas de resolución
- Si el arreglo es puramente mecánico (por ejemplo, un error tipográfico, una sección de instalación faltante en el README, o un formato erróneo en el CHANGELOG), abre un Pull Request solucionándolo.
- Si el arreglo requiere juicio técnico (por ejemplo, justificar la política de fanout, explicar la arquitectura pub/sub, o detallar la convergencia), abre un Issue detallando lo que falta y comenta exactamente la frase: "Requiere intervención humana: <motivo>".
- Bajo ninguna circunstancia fusiones los cambios directamente.
