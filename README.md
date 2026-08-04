# Simulador de N-Cuerpos con OpenMP - Laboratorio 1

## Roles del Equipo

| Miembro        | Rol / Contribucion                        |
|----------------|-------------------------------------------|
| **Benjamín Bustamante**   | Host/device y
memoria R2 |
| **Ignacio Solar**   | Kernels CUDA R1 |
| **Fabián Lizama**   | Git, releases y
agentes R4 |
| **Benjamín Sepúlveda**   | Integración y
validación R3 |
| **Josepha Gaete**   | Calidad, CI y visualizacion R5 |

## Kanban Lab 2 CUDA — Sub-issues y responsables

Desglose propuesto para cerrar la organización del issue #14, alineado con los roles del equipo:

| Sub-issue | Alcance | Responsable sugerido |
|-----------|---------|----------------------|
| 14-1 | [R5] Docker CUDA base oficial + build con `nvcc` (ref. #8) | **Josepha Gaete** (Calidad, CI y visualizacion) |
| 14-2 | [R2] Capa host/device (SoA + buffers RAII) + contrato de buffers/transferencias | **Benjamín Bustamante** (Modelo y datos) |
| 14-3 | [R1] Kernel CUDA básico de aceleraciones + firma final kernel/launcher | **Ignacio Solar** (Nucleo paralelo) |
| 14-4 | [R3] Integrar `computeAccelerationsGpu(...)` y `stepEulerGpu()` al simulador | **Fabián Lizama** (Integracion y fisica) |
| 14-5 | [R3] `calculateEnergyGpu()` (reducción + `atomicAdd`) | **Fabián Lizama** (Integracion y fisica) |
| 14-6 | [R3] Harness y tests CPU vs GPU (`N=2`, `N=3`, regresión completa; ref. #7) | **Josepha Gaete** (Calidad, CI y visualizacion) |
| 14-7 | [R1] Kernel con shared memory (tiles + sincronización) | **Ignacio Solar** (Nucleo paralelo) |
| 14-8 | [R5] Benchmarks (kernel-only, end-to-end, sweep `blockDim.x`) | **Benjamín Sepúlveda** (Metricas y benchmarks) |
| 14-9 | [R4] Checklist DoD por PR + gate CI obligatorio + cierre formal flujo Git/roles/agentes (ref. #1) | **Josepha Gaete** (Calidad, CI y visualizacion) |
| 14-10 | [R4] Actualizar `README.md` y `CHANGELOG.md` con resultados finales | **Benjamín Sepúlveda** (Metricas y benchmarks) |

## Decisiones de Diseno

### Arquitectura Orientada a Objetos
- **`Particle`**: Encapsula estado posicion/velocidad/aceleracion/masa de cada cuerpo.
- **`NBodySimulator`**: Contiene el vector de particulas y coordina el calculo de fuerzas, energia e integracion.
- **`Integrator`**: Clase estatica que implementa el integrador de Euler con distintas estrategias de sincronizacion OpenMP.
- **`MetricsCalculator`**: Metodos estaticos para calcular momento lineal, centro de masas, radio RMS y distancia minima.
- **`Benchmark`**: Encapsula medicion de tiempos con repeticiones estadisticas, propagacion de errores y calculo de metricas (speedup, eficiencia, fraccion serial de Amdahl).
- **`Visualizer`**: Responsabilidad unica de exportar estados del sistema a archivos `.dat`.

### Justificación del paso de tiempo (dt)
Se eligio `dt = 0.01` por las siguientes razones:
1. Estabilidad numerica: con `G = 1.0` y velocidades maximas de `~1.0`, el desplazamiento maximo por paso es `~0.01` unidades, mucho menor que el radio tipico de configuracion (`10.0` unidades).
2. Precision: paso suficientemente pequeno para que la aceleracion no varie significativamente entre pasos, garantizando validez del integrador Euler de primer orden.
3. Costo computacional: permite 100 pasos en tiempos razonables incluso con 2000 particulas, facilitando la recoleccion de datos estadisticos.

### Orden de integracion (Euler Simplectico)
El integrador sigue el esquema de **Euler simplectico** (tambien conocido como semi-implicito):
1. Se calculan todas las aceleraciones `a_i` (en `computeAccelerations()`).
2. Para cada particula, se actualiza primero la velocidad (`kick`: `v_i += a_i * dt`) y luego la posicion con la velocidad recien actualizada (`drift`: `r_i += v_i * dt`).

Este orden (kick-drift en el mismo bucle) es **matematicamente equivalente** a hacer todos los kicks primero y todos los drifts despues, gracias a que la deriva de cada particula solo depende de su propia velocidad. La fusion de bucles es una optimizacion valida que no altera el resultado fisico. Ademas, el Euler simplectico tiene mejores propiedades de conservacion de energia que el Euler explicito tradicional.

### Condiciones iniciales
Los cuerpos se inicializan mediante distribuciones aleatorias uniformes con semilla fija (42):
- **Posiciones**: distribucion uniforme en el rango `[-10.0, 10.0]` para ambas coordenadas `x` e `y`.
- **Velocidades**: distribucion uniforme en el rango `[-1.0, 1.0]` para ambas componentes `vx` y `vy`.
- **Masas**: distribucion uniforme en el rango `[0.5, 2.0]`.

La semilla puede sobreescribirse pasando un entero como primer argumento (ej. `./nbody_sim 123`).

### Unidades adimensionales
Al fijar `G = 1.0`, se define un sistema adimensional coherente: todas las posiciones, tiempos y masas se expresan en unidades de simulacion relativas (u.s.). No hay conversion a unidades fisicas (kg, m, s). La suavizacion `epsilon = 0.1` y el paso `dt = 0.01` son consistentes con este sistema adimensional.

### Criterio de tolerancia en comparaciones de coma flotante
- **Pruebas de fuerza analitica**: tolerancia de `1e-5` para verificar la formula general de aceleracion con epsilon de suavizado.
- **Pruebas de momento y centro de masas**: tolerancia de `1e-9` para verificar valores analiticamente esperados (cero o valores exactos).
- **Pruebas de accion-reaccion**: tolerancia de `1e-5` para la tercera ley de Newton.
- **Pruebas de regresion**: se verifica que los valores sean finitos (`std::isfinite()`) ante condiciones extremas (distancias casi nulas, masas negativas).

#### Tolerancias para comparacion CPU vs GPU (Lab 2)
La equivalencia entre resultados de CPU (referencia serial) y GPU se verifica mediante
comparacion en coma flotante con tolerancias relativa (`rtol`) y absoluta (`atol`),
definidas en `tests/gpu_test_helpers.h`:

| Parametro | Valor | Descripcion |
|-----------|-------|-------------|
| `rtol` | **1e-4** | Tolerancia relativa. La diferencia entre dos valores `a` y `b` se considera aceptable si `|a - b| <= atol + rtol * max(|a|, |b|)`. Un `rtol` de 1e-4 equivale a exigir al menos 4 digitos significativos de coincidencia respecto a la magnitud del valor. |
| `atol` | **1e-8** | Tolerancia absoluta. Actua como piso minimo de comparacion para valores cercanos a cero, donde la tolerancia relativa perderia sentido. Un `atol` de 1e-8 garantiza que diferencias menores a este umbral se consideren identicas, independientemente de la magnitud. |

Estos valores fueron sugeridos por el laboratorio para aceleraciones y son consistentes
con el error de redondeo esperado en operaciones de suma acumulativa en GPU (orden de
reduccion no deterministico y precision `float`/`double` en kernels CUDA). La infraestructura
de comparacion esta implementada en `tests/gpu_test_helpers.h` y es utilizada por los
tests de equivalencia en `tests/test_gpu_equivalence.cpp`.

## Cláusulas OpenMP Implementadas

| Clausula / Directiva | Archivo | Metodo |
|---------------------|---------|--------|
| `schedule(static)` | `NBodySimulator.cpp` | `computeAccelerations()` / `computeAccelerationsSoA()` |
| `schedule(static)` / `schedule(dynamic)` / `schedule(guided)` | `NBodySimulator.cpp` | `computeAccelerations(int)` |
| `schedule(static, chunk)` / `schedule(dynamic, chunk)` / `schedule(guided, chunk)` | `NBodySimulator.cpp` | `computeAccelerations(int, int)` |
| `schedule(dynamic, 8)` + `reduction(min:)` + `simd` | `MetricsCalculator.cpp` | `calculateMinDistance()` |
| `parallel for simd` + `reduction(+:)` | `MetricsCalculator.cpp` | `calculateTotalMomentum()`, `calculateCenterOfMass()`, `calculateRMSRadius()` |
| `parallel for simd` + `reduction(+:)` | `NBodySimulator.cpp` | `calculateEnergy()` y bucles de fuerza |
| `atomic` | `NBodySimulator.cpp` | `calculateEnergy(kin, pot, 1)` |
| `atomic` | `Integrator.cpp` | `integrateEuler(ATOMIC)` |
| `critical` | `Integrator.cpp` | `integrateEuler(CRITICAL)` |
| `nowait` | `NBodySimulator.cpp` | `integrateEuler(dt, st, true)` y `simulatePhasesBarrier()` |
| `barrier` | `NBodySimulator.cpp` | `simulatePhasesBarrier()` y `integrateEuler(dt, st, true)` |
| `single` | `NBodySimulator.cpp` | `parallelInitializationSingle()` y `processBodies()` |
| `task` / `taskgroup` | `NBodySimulator.cpp` | `processBodies(int, bool)` |
| `firstprivate` | `NBodySimulator.cpp` | `processBodies(int, bool)` y `calculateMetricsFirstprivate()` |
| `lastprivate` | `NBodySimulator.cpp` | `calculateFinalStateLastprivate()` |
| `private` (explicito) | `NBodySimulator.cpp` | `calculateEnergy(kin, pot, method, true)` |

## Instrucciones de Compilacion y Ejecucion

### Requisitos Previos
- g++ con soporte OpenMP (`-fopenmp`)
- GNU Make
- (Opcional) Python 3 + NumPy + Matplotlib para generacion de graficos
- (Opcional) Docker para entorno reproducible

### Compilacion
```bash
make clean && make
```

### Ejecucion
```bash
./nbody_sim                    # Modo fisica: exporta estados y metricas
./nbody_sim --benchmark        # Modo benchmark: mide escalabilidad (hilos)
./nbody_sim --benchmark-all    # Modo benchmark completo: schedules, chunks, sync
```


### Nota de rendimiento c7a / SIMD

La implementacion actual conserva solo el kernel de fuerzas `soa`, que fue el ganador en las pruebas sobre c7a.48xlarge. Se separan `x`, `y` y `mass` en arreglos contiguos alineados a 64 bytes y se usa bloqueo de cache para favorecer SIMD/cache blocking. Para una explicacion detallada de vectorizacion, AVX-512, cache, false sharing, NUMA y herramientas de profiling, ver [`PERFORMANCE_NOTES.md`](PERFORMANCE_NOTES.md).

### Parametros de benchmark
Los modos de ejecucion aceptan parametros para reproducir corridas mas largas o barrer tamanos
de problema sin recompilar:

```bash
./nbody_sim --benchmark-all --bodies 4000 --steps 500 --repetitions 10 --threads 1,2,4,8,16
make analysis ARGS="--bodies 4000 --steps 500 --repetitions 10 --threads 1,2,4,8,16"
```

Opciones disponibles:
- `--bodies N`: numero de cuerpos.
- `--steps N`: pasos temporales.
- `--dt X`: paso de tiempo.
- `--epsilon X`: suavizado gravitatorio.
- `--seed N`: semilla reproducible.
- `--repetitions N`: repeticiones del benchmark principal.
- `--extra-repetitions N`: repeticiones para schedules, chunks y sincronizacion.
- `--threads 1,2,4,8,16`: lista de hilos a medir.
- `--variant-threads N`: hilos usados en benchmarks de variantes OpenMP.
- `--force-mode soa`: se mantiene por compatibilidad con scripts; esta version limpia solo incluye el kernel SoA. Default: `soa`.

En Slurm, `run_cluster.slurm` ejecuta una corrida parametrizable y `run_bodies_sweep.slurm`
barre varios valores de `N`, guardando resultados en `results/N...`.

### Pruebas Automatizadas
```bash
make test
```

### Analisis Completo (Benchmark + Graficos)
```bash
make analysis
```

### Docker

El `Dockerfile` usa la imagen base oficial sugerida por el enunciado,
`nvidia/cuda:12.4.1-devel-ubuntu22.04` (incluye CUDA Toolkit 12.4 y `nvcc`).
El `Makefile` detecta automaticamente los archivos en `kernels/*.cu`
(`wildcard`) y, si `nvcc` esta disponible, los compila y los linkea junto al
resto del binario con `-lcudart`, agregando `-DNBODY_ENABLE_CUDA_KERNELS`.

**Importante:** ese mismo flag tambien agrega `-I$(CUDA_HOME)/include` a los
flags de `g++` (no solo a los de `nvcc`). Sin ese include, `g++` —que
compila `NBodySimulator.cpp` y el resto de los `.cpp`— no ve
`<cuda_runtime.h>`, y `CudaBuffer.h` cae a un fallback de
`malloc` de host en esa unidad de compilacion, aunque el kernel real
(compilado por `nvcc`) si espere punteros de device reales. El sintoma en
GPU real habria sido un crash o datos corruptos al lanzar el kernel con
punteros de host disfrazados de punteros de device. Verificado con
`__has_include(<cuda_runtime.h>)` dentro del contenedor antes y después del
fix.

**Requisitos en el host:**
- Driver NVIDIA >= `550.54.14` (Linux) para CUDA 12.4. Verificar con
  `nvidia-smi` (la fila "CUDA Version" debe ser >= 12.4).
- [`nvidia-container-toolkit`](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  instalado y configurado como runtime de Docker, para poder pasar `--gpus all`.
- Sin GPU/driver NVIDIA en el host, la imagen igual compila (nvcc no
  requiere GPU física para compilar), pero no se pueden ejecutar kernels.

**Build y ejecución local:**
```bash
docker build -t nbody-cuda .

# compilar y correr la suite de tests (CPU; no requiere --gpus)
docker run --rm nbody-cuda make test

# con acceso a GPU (una vez existan tests/kernels GPU)
docker run --rm --gpus all nbody-cuda make test

# flujo por defecto de la imagen (benchmark + graficos, ver run_batch.sh)
docker run --rm --gpus all nbody-cuda
```

**Verificar que `nvcc` esté disponible dentro del contenedor:**
```bash
docker run --rm nbody-cuda make cuda-info
```

**`make test` vs `make test-gpu`:** `make test` compila y corre siempre en
modo CPU-only (no agrega `-DNBODY_ENABLE_CUDA_KERNELS`), a proposito: asi CI
sigue en verde en runners sin GPU (nvcc puede estar presente sin que haya un
device real, y un `cudaMalloc` real ahi falla). `make test-gpu` si compila
contra el kernel CUDA real y solo tiene sentido en una maquina con GPU
NVIDIA real (ej. el nodo GPU del cluster DIINF) — en cualquier otra maquina
falla con un error de CUDA (driver ausente), lo cual es el comportamiento
esperado, no un bug.

### Benchmarks GPU

`./nbody_sim --benchmark-gpu` (o `make benchmark-gpu`) corre la matriz
obligatoria de la sección 8.2 del enunciado: para cada combinacion de
`N` × variante `{0=básica, 1=shared memory}` × `blockDim.x`, mide con
`Benchmark::benchmarkKernelOnly` (solo el kernel + `cudaDeviceSynchronize`,
sin transferencias) y `Benchmark::benchmarkEndToEnd` (`computeAccelerationsGpu`,
con transferencias H2D/D2H incluidas), usando `std::chrono::steady_clock` en
host (no `cudaEvent_t`, como pide el enunciado) y `--repetitions` corridas por
punto (default 10).

Los tres ejes de la matriz son configurables (los defaults reproducen la
matriz original del enunciado):

- `--gpu-n-values LISTA` — valores de `N` separados por coma (default
  `256,512,1024,2000`).
- `--gpu-block-sizes LISTA` — valores de `blockDim.x` separados por coma
  (default `64,128,256,512,1024`).
- `--gpu-variants LISTA` — variantes de kernel separadas por coma (default
  `0,1`).

`--bodies`/`--steps` se ignoran en este modo: usa `--gpu-n-values` en su lugar.

```bash
# En una maquina/nodo con GPU NVIDIA real:
make benchmark-gpu ARGS="--repetitions 10"
# o directamente:
./nbody_sim --benchmark-gpu --repetitions 10

# Barrido de N mas grande (p. ej. en un nodo con GPU H100, mas memoria disponible):
./nbody_sim --benchmark-gpu --repetitions 10 --gpu-n-values 1000,5000,10000,20000
```

Salidas: `blockdim_study.dat` (kernel-only vs. end-to-end por punto de la
matriz) y `gpu_benchmark_results.dat` (comparación CPU serial vs. GPU
end-to-end y speedup con propagación de error, una fila por `(N, variante)`
con `blockDim.x=256`).

**Graficos:** `make benchmark-gpu` corre el binario y automaticamente llama a
`plot_gpu_benchmarks.py`, que lee esos dos `.dat` y genera
`gpu_performance_plots.png` con los 4 graficos GPU requeridos en la seccion
11.1 del enunciado: speedup GPU vs. CPU vs. N, kernel-only vs. end-to-end,
tiempo vs. `blockDim.x` (ambas variantes) y basica vs. shared memory. Si
se corre el script sin haber generado los `.dat` (p. ej. en esta laptop, sin
GPU), cada panel simplemente muestra "Datos no disponibles" en vez de
fallar, asi se puede probar el pipeline de principio a fin sin GPU.

Requiere un binario compilado con `NBODY_ENABLE_CUDA_KERNELS` (ver arriba) y
una GPU NVIDIA real; sin eso falla con un mensaje explicito en vez de
inventar numeros. **Las corridas que van al reporte final deben hacerse en
el nodo GPU del cluster DIINF**, no en CI ni en una laptop sin GPU (sección
8.3 del enunciado).

**Caveat de variant=1:** el kernel con memoria compartida (issue [#20](https://github.com/solarc3/distri-l1-126/issues/20),
rol Kernels CUDA) todavia no está integrado — `launchComputeAccelerations`
ignora el parametro `variant` y siempre ejecuta el kernel basico. El barrido
ya soporta `variant=1` en la API/CLI, pero hasta que el kernel shared se
mergee, sus numeros seran identicos a `variant=0`. Hay que volver a correr
la matriz cuando eso ocurra.

### CI / gate de fusión a `main`

El pipeline (`.github/workflows/ci.yml`) corre en cada Pull Request contra
`main`/`master` con dos jobs obligatorios:

| Job | Qué valida |
|-----|------------|
| `build-and-test` | `make` + `make test` en un runner nativo Ubuntu (sin Docker) |
| `docker-cuda-build` | `docker build` de la imagen CUDA + `docker run ... make test` dentro del contenedor |

Ambos deben quedar en verde antes de fusionar. Para que GitHub bloquee el
merge si la CI falla, `main` debe tener una regla de protección de rama con
"Require status checks to pass before merging" apuntando a `build-and-test`
y `docker-cuda-build` (Settings → Branches → Branch protection rules). Un
job con GPU real en CI es opcional y no se usa para las mediciones finales
de rendimiento: esas solo se aceptan desde el nodo GPU del clúster DIINF.

## Archivos de Salida

| Archivo | Descripcion |
|---------|-------------|
| `energy_timeseries.dat` | Series temporales de energia (cinetica, potencial, total) y metricas fisicas por paso |
| `state_XXXX.dat` | Instantaneas de posiciones/velocidades de todas las particulas |
| `benchmark_results.dat` | Resultados del benchmark de escalabilidad (tiempos, speedup, eficiencia) |
| `scaling_analysis.dat` | Datos de escalamiento con curva teorica de Amdahl |
| `schedule_benchmark.dat` | Comparacion de schedules (static, dynamic, guided) |
| `chunk_benchmark.dat` | Tiempo vs tamanio de chunk para cada schedule |
| `sync_benchmark.dat` | Comparacion de estrategias de sincronizacion (atomic, critical, nowait, normal) |
| `performance_plots.png` | Graficos: speedup, eficiencia, tiempo, Amdahl, chunk, energia |
| `blockdim_study.dat` | (`--benchmark-gpu`) Kernel-only vs. end-to-end por `N`/variante/`blockDim.x` |
| `gpu_benchmark_results.dat` | (`--benchmark-gpu`) CPU vs. GPU end-to-end y speedup por `N`/variante |
| `gpu_performance_plots.png` | Graficos GPU: speedup vs. N, kernel-only vs. end-to-end, tiempo vs. blockDim.x, basica vs. shared |

## Estructura del Proyecto

```
.
├── Particle.h/.cpp          # Clase particula
├── NBodySimulator.h/.cpp    # Simulador principal con sobrecargas OpenMP
├── Integrator.h/.cpp        # Integrador de Euler (multi-estrategia)
├── Benchmark.h/.cpp         # Medicion de rendimiento y propagacion de errores
├── MetricsCalculator.h/.cpp # Calculo de metricas fisicas con OpenMP
├── Visualizer.h/.cpp        # Exportacion de estados a archivos .dat
├── main.cpp                 # Punto de entrada con modos fisica/benchmark
├── Makefile                 # Compilacion, test, benchmark, analisis
├── plot_performance.py      # Graficos CPU/OpenMP
├── plot_gpu_benchmarks.py   # Graficos GPU (--benchmark-gpu)
├── Dockerfile               # Contenedor reproducible (base nvidia/cuda + nvcc)
├── kernels/                 # Kernels CUDA: accelerations.cu/.cuh (basico); shared memory pendiente (#20)
├── .github/                 # CI con GitHub Actions (build-and-test + docker-cuda-build)
├── tests/
│   ├── test_physics.cpp         # Pruebas unitarias y de regresion con GTest
│   ├── test_gpu_equivalence.cpp # Pruebas de equivalencia CPU vs GPU (esqueleto Lab 2)
│   └── gpu_test_helpers.h       # Helpers de comparacion con tolerancias (rtol, atol)
└── README.md                # Este archivo
```
