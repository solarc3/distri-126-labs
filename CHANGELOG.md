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
- `plot_gpu_benchmarks.py`: genera `gpu_performance_plots.png` (speedup GPU vs. CPU vs. N, kernel-only vs. end-to-end, tiempo vs. blockDim.x, basica vs. shared memory) a partir de esos `.dat`, invocado automaticamente por `make benchmark-gpu`.
- Target `make test-gpu` para validar el kernel CUDA real (vs. `make test`, que se mantiene CPU-only para no romper CI sin GPU).

### Changed
- (Espacio reservado para los cambios de CPU a GPU)
- `Makefile`: el `-arch=sm_80` único se reemplaza por fatbinary multi-gencode (`CUDA_GENCODE`: SASS sm_75/sm_80/sm_86/sm_90 + PTX compute_90), para que la misma imagen Docker ejecute nativo en g4dn (T4), p4d (A100), g5 (A10G) y H100, con forward-compat vía JIT en GPUs más nuevas. Los gencode se aplican en la receta de `nvcc` y no dentro de `NVCCFLAGS`, para que un override de `NVCCFLAGS` por línea de comandos no los descarte silenciosamente (revisión PR #73).
- `Dockerfile`: el build horneado en la imagen usa `MARCH_FLAGS="-march=x86-64-v3"` en vez de `-march=native`; un binario nativo del build host (Zen 4, AVX-512) haría SIGILL en CPUs sin AVX-512 (Ice Lake en g5, Zen 3 en xigpu). `run_batch.sh` sigue recompilando con `-march=native` al iniciar el contenedor, así que los benchmarks corren nativos en el target (revisión PR #73).

### Fixed
- `Makefile`: se agregó `-I$(CUDA_HOME)/include` a los flags de `g++` cuando CUDA está habilitado. Sin ese include, `CudaBuffer.h` caía a un fallback de `malloc` de host en las unidades de compilación host (`NBodySimulator.cpp`, etc.) aunque el kernel real esperara punteros de device, lo que habría causado un crash o corrupción de memoria al correr en una GPU real (issue #39).

## [2.0.0-lab2] - 2026-07-24
*(Esta sección se completará el día de la entrega final)*
