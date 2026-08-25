---
engine:
  id: copilot
  model: gpt-4o
max-ai-credits: 200
on:
  schedule: daily
permissions:
  contents: read
  issues: read
  pull-requests: read
safe-outputs:
  create-issue:
    labels: [bug, gossip, pubsub, agent]
  create-pull-request:
    title-prefix: "[bugfix] "
---
## Tarea del Agente
Analiza el código Python de `civicmesh/` y `tests/` en busca de malas prácticas, regresiones o errores. Verifica exhaustivamente la capa de membresía (gossip), el enrutamiento (pub/sub), las suscripciones, y el parseo de mensajes. Revisa también que la semilla del generador aleatorio se comporte determinísticamente en tests y repeticiones.

## Reglas de resolución
- Si el fix es mecánico (por ejemplo, corrección de tipado en diccionarios de estado, o aserciones de tests unitarios erróneas sobre formato), abre un Pull Request o Issue con el parche sugerido.
- Si el problema detectado afecta la lógica central de membresía (gossip), el protocolo pub/sub (el criterio `should_forward`), o la semántica del dominio (delitos/aire), abre un Issue y comenta exactamente: "requiere intervención humana".
