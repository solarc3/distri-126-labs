# Simulador de N-Cuerpos con OpenMP - Laboratorio 1

## Roles del Equipo

| Miembro        | Rol / Contribucion                        |
|----------------|-------------------------------------------|
| **[Nombre]**   | Modelo y datos |
| **[Nombre]**   | Nucleo paralelo |
| **[Nombre]**   | Integracion y fisica |
| **[Nombre]**   | Metricas y benchmarks |
| **[Nombre]**   | Calidad, CI y visualizacion |

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

## Cláusulas OpenMP Implementadas

| Clausula / Directiva | Archivo | Metodo |
|---------------------|---------|--------|
| `schedule(dynamic)` | `NBodySimulator.cpp` | `computeAccelerations()` (defecto) |
| `schedule(static)` / `schedule(dynamic)` / `schedule(guided)` | `NBodySimulator.cpp` | `computeAccelerations(int)` |
| `schedule(static, chunk)` / `schedule(dynamic, chunk)` / `schedule(guided, chunk)` | `NBodySimulator.cpp` | `computeAccelerations(int, int)` |
| `collapse(2)` | `NBodySimulator.cpp` | `computeAccelerationsCollapse()` |
| `collapse(2)` + `reduction(min:)` | `MetricsCalculator.cpp` | `calculateMinDistance()` |
| `reduction(+:)` | `MetricsCalculator.cpp` | `calculateTotalMomentum()`, `calculateCenterOfMass()`, `calculateRMSRadius()` |
| `reduction(+:)` | `NBodySimulator.cpp` | `calculateEnergy()` |
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

### Pruebas Automatizadas
```bash
make test
```

### Analisis Completo (Benchmark + Graficos)
```bash
make analysis
```

### Docker
```bash
docker build -t nbody-sim .
docker run --rm nbody-sim make test
```

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
├── plot_performance.py      # Script de generacion de graficos
├── Dockerfile               # Contenedor reproducible
├── .github/                 # CI con GitHub Actions
├── tests/
│   └── test_physics.cpp     # Pruebas unitarias y de regresion con GTest
└── README.md                # Este archivo
```
