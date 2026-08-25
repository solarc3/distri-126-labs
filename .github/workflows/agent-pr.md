---
engine:
  id: copilot
  model: gpt-4o
on:
  pull_request:
    types: [opened, synchronize]
permissions:
  contents: read
  pull-requests: read
  issues: read
safe-outputs:
  add-comment: {}
---
## Tarea del Agente
Revisa el código modificado (diff) de este Pull Request y el estado de los tests en la Integración Continua (CI). Clasifica el Pull Request según su impacto en el framework P2P CivicMesh. Al inicio de tu comentario, agrega el prefijo "[IA Review]".

## Reglas de resolución
- Tu revisión y comentario deben realizarse **después** de que el pipeline de CI haya finalizado.
- Si los cambios son solo de documentación, formato, o son tests que pasan exitosamente y NO alteran el estado compartido o la latencia de descubrimiento: deja un comentario exacto que diga "mecánico y mergeable".
- Si el cambio altera el comportamiento de la red, modifica el fanout, el protocolo de ruteo, o la lógica de los publicadores, deja un comentario exacto que diga "requiere revisión humana".
- Si el pipeline de CI falló, tu comentario debe indicarlo explícitamente al inicio.
- NUNCA realices un merge automático a `main`.
