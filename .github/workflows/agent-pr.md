---
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
Revisa el código modificado (diff) de este Pull Request y el estado de los tests en la Integración Continua (CI). Clasifica el Pull Request según su impacto en el simulador N-cuerpos. Al inicio de tu comentario, agrega el prefijo "[IA Review]".

## Reglas de resolución
- Si los cambios son solo de documentación, formato, o son tests que pasan exitosamente y NO alteran la semántica física del simulador ni cambian firmas públicas sin un issue asociado: deja un comentario exacto que diga "mecánico y mergeable".
- Si el cambio altera el comportamiento físico, modifica el uso de memoria (ej. SoA vs AoS, uso de `__shared__`), o altera los kernels, deja un comentario exacto que diga "requiere revisión humana".
- Si el pipeline de CI falló, tu comentario debe indicarlo explícitamente al inicio.
- NUNCA realices un merge automático.
