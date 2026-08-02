# Changelog

Todos los cambios notables de este proyecto (Simulador gravitatorio N-cuerpos en 2D) se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/), y este proyecto se adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Configuración inicial de agentes de IA (Documentador, Bugs, MRs) usando GitHub Agentic Workflows.
- Reglas de protección de rama y flujos de revisión automatizados.
- Se documentó en `README.md` el desglose de sub-issues propuestos para CUDA Lab 2 y su asignación por rol de equipo (issue #14).
- `Dockerfile` migrado a `nvidia/cuda:12.4.1-devel-ubuntu22.04`; CI extendida con job `docker-cuda-build` (issue #8).
- Matriz de benchmarks GPU (`--benchmark-gpu` / `make benchmark-gpu`): `Benchmark::benchmarkKernelOnly`, `Benchmark::benchmarkEndToEnd` y `Benchmark::compareCpuGpu`, con salida en `blockdim_study.dat` y `gpu_benchmark_results.dat` (issue #39).
- Target `make test-gpu` para validar el kernel CUDA real (vs. `make test`, que se mantiene CPU-only para no romper CI sin GPU).

### Changed
- (Espacio reservado para los cambios de CPU a GPU)

### Fixed
- `Makefile`: se agregó `-I$(CUDA_HOME)/include` a los flags de `g++` cuando CUDA está habilitado. Sin ese include, `CudaBuffer.h` caía a un fallback de `malloc` de host en las unidades de compilación host (`NBodySimulator.cpp`, etc.) aunque el kernel real esperara punteros de device, lo que habría causado un crash o corrupción de memoria al correr en una GPU real (issue #39).

## [2.0.0-lab2] - 2026-07-24
*(Esta sección se completará el día de la entrega final)*
