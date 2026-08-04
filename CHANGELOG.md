# Changelog

Todos los cambios notables de este proyecto (Simulador gravitatorio N-cuerpos en 2D) se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/), y este proyecto se adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0-lab2] - 2026-08-04

Portación del núcleo computacional del simulador N-cuerpos 2D a GPU con CUDA.
Mediciones finales ejecutadas en el nodo GPU del clúster DIINF (`xigpu01`,
2× NVIDIA A30 24 GB, driver 580.173.02, CUDA 12.4.131).

### Added
- Configuración inicial de agentes de IA (Documentador, Bugs, MRs) usando GitHub Agentic Workflows.
- Reglas de protección de rama y flujos de revisión automatizados.
- Se documentó en `README.md` el desglose de sub-issues propuestos para CUDA Lab 2 y su asignación por rol de equipo (issue #14).
- `Dockerfile` migrado a `nvidia/cuda:12.4.1-devel-ubuntu22.04`; CI extendida con job `docker-cuda-build` (issue #8).
- Matriz de benchmarks GPU (`--benchmark-gpu` / `make benchmark-gpu`): `Benchmark::benchmarkKernelOnly`, `Benchmark::benchmarkEndToEnd` y `Benchmark::compareCpuGpu`, con salida en `blockdim_study.dat` y `gpu_benchmark_results.dat` (issue #39).
- `plot_gpu_benchmarks.py`: genera `gpu_performance_plots.png` (speedup GPU vs. CPU vs. N, kernel-only vs. end-to-end, tiempo vs. blockDim.x, basica vs. shared memory) a partir de esos `.dat`, invocado automaticamente por `make benchmark-gpu`.
- Target `make test-gpu` para validar el kernel CUDA real (vs. `make test`, que se mantiene CPU-only para no romper CI sin GPU).
- Soporte multi-GPU: `NBodySimulator::resolveGpuDeviceCount()` consulta `cudaGetDeviceCount()` en runtime y `splitParticleRange()` (`GpuDeviceSplit.h`) reparte las partículas de salida en slices contiguos balanceados, uno por device. Cada GPU recibe las N posiciones completas y calcula solo su rango; los kernels se lanzan de forma asíncrona en el stream por defecto de cada device y se sincronizan en un segundo loop, de modo que corren en paralelo real. `setGpuDeviceLimit()` permite acotar el número de devices (issue #75).
- `--gpu-skip-cpu`: omite `compareCpuGpu()` para medir solo la matriz GPU. La referencia CPU O(N²) × repeticiones domina el wall time a N grande.
- `run_gpu_diinf.sh`: barrido GPU reproducible para el nodo DIINF dentro del contenedor pyxis/enroot. Smoke test GPU previo, una invocación del binario por cada N (los `.dat` se abren con truncate), archivado y subida incremental a S3 tras cada N.
- `aws/nbody-gpu-uploader-policy.json`: política IAM de permiso mínimo para publicar los resultados del clúster en S3 (escritura acotada al prefijo `gpu-diinf/`, sin borrado ni acceso al resto del bucket).

### Changed
- Núcleo de cálculo de aceleraciones portado a CUDA con dos variantes obligatorias: `computeAccelerationsKernel` (un hilo por cuerpo *i*, bucle serial sobre *j*) y `computeAccelerationsKernelShared` (tiling de posiciones y masas en `__shared__` con `__syncthreads()` entre carga y uso). La referencia CPU serial del Lab 1 se conserva intacta como fuente de verdad para regresión.
- `Makefile`: el `-arch=sm_80` único se reemplaza por fatbinary multi-gencode (`CUDA_GENCODE`: SASS sm_75/sm_80/sm_86/sm_90 + PTX compute_90), para que la misma imagen Docker ejecute nativo en g4dn (T4), p4d (A100), g5 (A10G) y H100, con forward-compat vía JIT en GPUs más nuevas. Los gencode se aplican en la receta de `nvcc` y no dentro de `NVCCFLAGS`, para que un override de `NVCCFLAGS` por línea de comandos no los descarte silenciosamente (revisión PR #73).
- `Dockerfile`: el build horneado en la imagen usa `MARCH_FLAGS="-march=x86-64-v3"` en vez de `-march=native`; un binario nativo del build host (Zen 4, AVX-512) haría SIGILL en CPUs sin AVX-512 (Ice Lake en g5, Zen 3 en xigpu). `run_batch.sh` sigue recompilando con `-march=native` al iniciar el contenedor, así que los benchmarks corren nativos en el target (revisión PR #73).

### Fixed
- `Makefile`: se agregó `-I$(CUDA_HOME)/include` a los flags de `g++` cuando CUDA está habilitado. Sin ese include, `CudaBuffer.h` caía a un fallback de `malloc` de host en las unidades de compilación host (`NBodySimulator.cpp`, etc.) aunque el kernel real esperara punteros de device, lo que habría causado un crash o corrupción de memoria al correr en una GPU real (issue #39).
- `main.cpp`: los `.dat` del benchmark GPU ahora se hacen flush tras cada fila. Ambos `ofstream` escribían sin flush hasta el cierre del programa y `gpu_benchmark_results.dat` emite una sola fila por `(N, variante)`, así que a N grande nunca llenaba el buffer de stdio: un timeout de Slurm se llevaba mediciones que sí se habían hecho, dejando el archivo con solo el header (issue #82).
- `main.cpp`: se añadió log de progreso al bucle CPU-vs-GPU, que antes pasaba minutos sin emitir nada y era indistinguible de un cuelgue (issue #82).
- `main.cpp`: se corrigió la nota que afirmaba que `variant=1` ejecutaba el kernel básico por dentro. `launchComputeAccelerations()` despacha `variant=1` a `computeAccelerationsKernelShared` con memoria compartida real desde la integración del kernel shared; la nota obsoleta llevaba a descartar como inválidos resultados que sí lo son (PR #86).
- `plot_gpu_benchmarks.py`: un `.dat` sin filas de datos se trata como ausente. `np.loadtxt` devuelve un array vacío y el `reshape(1, -1)` lo dejaba en shape `(1, 0)`, haciendo fallar los paneles con `IndexError` (issue #82).
- `run_gpu_benchmark.slurm`: `trap EXIT` que rescata los resultados parciales aunque `make` falle bajo `set -e`; antes un fallo saltaba el `cp` a `results/` y se perdía todo. Además `--cpus-per-task=48`, `--time` explícito y `run_metadata.txt` con nodo, GPU, CPU y parámetros (issue #82).
- `run_gpu_diinf.sh`: el chequeo de build `strings ./nbody_sim | grep -q ...` abortaba el barrido con un binario correcto. `grep -q` cierra el pipe al primer match y `strings` muere con SIGPIPE (141), que bajo `set -o pipefail` hace fallar la tubería entera. Se reemplazó por un smoke test que ejecuta un punto mínimo de la matriz contra la GPU real (PR #85).

## [1.0.0-lab1] - 2026-06-15
Versión CPU del Laboratorio 1 (OpenMP), conservada como baseline de corrección
y referencia para los benchmarks comparativos de este laboratorio.
