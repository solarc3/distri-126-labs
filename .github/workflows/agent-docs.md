---
engine:
  id: copilot
  model: gpt-5-mini
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
Revisa el estado de la documentación en el repositorio, específicamente el `README.md`, el `CHANGELOG.md` y los comentarios en los archivos de código C++ y cabeceras.

## Reglas de resolución
- Si el arreglo es puramente mecánico (por ejemplo, un error tipográfico, una sección faltante en el README con una plantilla obvia, o un enlace roto), abre un Pull Request solucionándolo.
- Si el arreglo requiere juicio técnico (por ejemplo, explicar el funcionamiento de un kernel con memoria compartida o decisiones de diseño), abre un Issue detallando lo que falta y comenta exactamente la frase: "Requiere intervención humana: <motivo>".
- Bajo ninguna circunstancia fusiones los cambios directamente.
