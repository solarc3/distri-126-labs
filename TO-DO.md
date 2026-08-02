# Kanban Lab 2 CUDA — Organización de Equipo

> Asignaciones basadas en los roles actuales definidos en `/home/runner/work/distri-l1-126/distri-l1-126/README.md`.
> Última actualización: 2026-08-02 — revisión completa de issues/PR en GitHub.

## 🟥 Backlog (priorizado)
- [ ] [R1] Kernel con shared memory (tiles + sincronización) — #20 — Responsable: **Ignacio Solar**
- [ ] [R1] Kernel básico + borde `i >= N` — #22 — Responsable: **Ignacio Solar**
- [ ] [R3] `calculateEnergyGpu()` con `atomicAdd` — Responsable: **Benjamín Sepúlveda**
- [ ] [R5] Benchmarks: kernel-only, end-to-end, sweep `blockDim.x` — #39 — Responsable: **Josepha Gaete**
- [ ] [R4] Cierre formal de flujo Git/roles/agentes (Refs #1) — #1 — Responsable: **Fabián Lizama**
- [ ] [R4/R5] Análisis Amdahl — Responsables: **Fabián Lizama** y **Josepha Gaete**
- [ ] [R4] Actualizar `README.md` y `CHANGELOG.md` con resultados finales — Responsable: **Fabián Lizama**
- [ ] Documentación y comentarios del código — #11 — Sin asignar
- [ ] Review Euler integration and memory management — #10 — Responsable: **Benjamín Sepúlveda**

## 🟨 To Do (tomables esta semana)
- [ ] [R4] Definir checklist de DoD por PR — Responsable: **Fabián Lizama**
- [ ] [R5] Dejar gate de CI obligatorio para merge — Responsable: **Josepha Gaete**
- [ ] [R1] Definir firma final de kernel/launcher — #21 — Responsable: **Ignacio Solar**

## 🟦 In Progress


## 🟪 Blocked (con dependencia explícita)
- [ ] [R1] Kernel shared memory bloqueado por kernel básico + borde `i >= N` — #20 — Responsable: **Ignacio Solar**
- [ ] [R5] Benchmarks finales bloqueados por validación CPU vs GPU (necesita mediciones completas) — #39 — Responsable: **Josepha Gaete**
- [ ] [R4/R5] Análisis Amdahl bloqueado por mediciones end-to-end — Responsables: **Fabián Lizama** y **Josepha Gaete**

## 🟩 Done (estado actual)
- [x] PR #2 mergeado: agentes IA + `CHANGELOG.md` base
- [x] PR #12 mergeado: fix safe outputs de agentes
- [x] PR #13 mergeado: integración transicional `computeAccelerationsKernel` (cierra #6)
- [x] PR #15 mergeado: documentación CUDA Lab 2 sub-issues y roles
- [x] PR #16 mergeado: creación de TO-DO.md (cierra #14)
- [x] PR #23 mergeado: [R3] harness de tests CPU vs GPU con tolerancias base (cierra #17)
- [x] PR #25 mergeado: [R2] capa host/device, layout SoA, gestión RAII (cierra #18)
- [x] PR #28 mergeado: [R3] harness modular de comparación CPU vs GPU (cierra #26)
- [x] PR #31 mergeado: fix Dockerfile, Makefile, CI (cierra #8)
- [x] PR #32 mergeado: [R1] kernel CUDA básico de aceleraciones (cierra #19)
- [x] PR #36 mergeado: [R3] integración `computeAccelerationsGpu()` + `stepEulerGpu()` al simulador (cierra #30)
- [x] PR #37 mergeado: [Validación] tests de equivalencia CPU vs GPU para aceleraciones (cierra #7)
- [x] PR #40 mergeado: [R3] implementar `stepEulerGpu()` con orden fijo del enunciado (cierra #38)
- [x] PR #43 mergeado: [R3] implementar `calculateEnergyGpu()` con reducción en shared memory (cierra #42)

---

## Reglas de movimiento
- To Do → In Progress: requiere responsable y criterio de aceptación.
- In Progress → Done: requiere PR + CI verde + revisión humana.
- Blocked: siempre indicar issue/PR que desbloquea.
