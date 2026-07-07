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
    labels: [bug, cuda, agent]
  create-pull-request:
    title-prefix: "[bugfix] "
---
## Tarea del Agente
Analiza el código C++ y CUDA (`.cu`, `.cuh`, `.cpp`, `.h`) en busca de malas prácticas, regresiones o errores. Verifica exhaustivamente que todas las llamadas a la API de CUDA estén envueltas en macros de manejo de errores (como `CUDA_CHECK`) y detecta posibles desincronizaciones entre host y device.

## Reglas de resolución
- Si el fix es mecánico (por ejemplo, falta un `CUDA CHECK` o un test falla porque la tolerancia de coma flotante fue mal copiada), abre un Pull Request o Issue con el parche sugerido.
- Si el problema detectado afecta la lógica de los kernels de aceleración, la API pública o el integrador Euler, abre un Issue y comenta exactamente: "Requiere intervención humana no modificar main directamente".
