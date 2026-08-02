# Kanban Lab 2 CUDA — Organización de Equipo

> Asignaciones basadas en los roles actuales definidos en `/home/runner/work/distri-l1-126/distri-l1-126/README.md`.

## 🟥 Backlog (priorizado)
- [ ] [R5] Docker CUDA base oficial + build con `nvcc` (Refs solarc3/distri-l1-126#8) — Responsable: **Josepha Gaete**
- [ ] [R2] Capa host/device (SoA + buffers RAII) — Responsable: **Benjamín Bustamante**
- [ ] [R1] Kernel CUDA básico de aceleraciones — Responsable: **Ignacio Solar**
- [ ] [R3] Integrar `computeAccelerationsGpu(...)` al simulador — Responsable: **Benjamín Sepúlveda**
- [ ] [R3] Tests CPU vs GPU: N=2, N=3 y regresión completa (Refs solarc3/distri-l1-126#7) — Responsable: **Benjamín Sepúlveda**
- [ ] [R1] Kernel con shared memory (tiles + sincronización) — Responsable: **Ignacio Solar**
- [ ] [R3] `stepEulerGpu()` con orden del enunciado — Responsable: **Benjamín Sepúlveda**
- [ ] [R3] `calculateEnergyGpu()` con reducción — Responsable: **Benjamín Sepúlveda**
- [ ] [R3] `calculateEnergyGpu()` con `atomicAdd` — Responsable: **Benjamín Sepúlveda**
- [ ] [R5] Benchmarks: kernel-only, end-to-end, sweep `blockDim.x` — Responsable: **Josepha Gaete**
- [ ] [R4] Cierre formal de flujo Git/roles/agentes (Refs solarc3/distri-l1-126#1) — Responsable: **Fabián Lizama**
- [ ] [R4] Actualizar `README.md` y `CHANGELOG.md` con resultados finales — Responsable: **Fabián Lizama**

## 🟨 To Do (tomables esta semana)
- [ ] [R4] Definir checklist de DoD por PR — Responsable: **Fabián Lizama**
- [ ] [R5] Dejar gate de CI obligatorio para merge — Responsable: **Josepha Gaete**
- [ ] [R2] Definir contrato de buffers y transferencias — Responsable: **Benjamín Bustamante**
- [ ] [R1] Definir firma final de kernel/launcher — Responsable: **Ignacio Solar**
- [ ] [R3] Preparar harness de comparación CPU vs GPU — Responsable: **Benjamín Sepúlveda**

## 🟦 In Progress
- [ ] [R5] Migración Dockerfile a CUDA — Responsable: **Josepha Gaete**
- [ ] [R2] Memoria device mínima (`x,y,mass,ax,ay`) — Responsable: **Benjamín Bustamante**
- [ ] [R1] Kernel básico + borde `i >= N` — Responsable: **Ignacio Solar**
- [ ] [R3] Esqueleto de tests con tolerancias base (`rtol`, `atol`) — Responsable: **Benjamín Sepúlveda**

## 🟪 Blocked (con dependencia explícita)
- [ ] [R1] Kernel shared bloqueado por kernel básico estable — Responsable: **Ignacio Solar**
- [ ] [R5] Benchmarks finales bloqueados por validación CPU vs GPU en verde — Responsable: **Josepha Gaete**
- [ ] [R4/R5] Análisis Amdahl bloqueado por mediciones end-to-end — Responsables: **Fabián Lizama** y **Josepha Gaete**
- [ ] [R3] Cierre solarc3/distri-l1-126#7 bloqueado por ruta GPU funcional en CI — Responsable: **Benjamín Sepúlveda**

## 🟩 Done (estado actual)
- [x] PR solarc3/distri-l1-126#2 mergeado: agentes IA + `CHANGELOG.md` base
- [x] PR solarc3/distri-l1-126#12 mergeado: fix safe outputs de agentes
- [x] PR solarc3/distri-l1-126#13 mergeado: integración transicional `computeAccelerationsKernel` (cierra solarc3/distri-l1-126#6)

---

## Reglas de movimiento
- To Do → In Progress: requiere responsable y criterio de aceptación.
- In Progress → Done: requiere PR + CI verde + revisión humana.
- Blocked: siempre indicar issue/PR que desbloquea.
