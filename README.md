<div align="center">
  <h3>Universidad de Santiago de Chile (USACH)</h3>
  <h4>Departamento de Ingeniería Informática (DIINF)</h4>
  <h1>Laboratorio 2: Simulación N-Body (CUDA / C++)</h1>
</div>

## Descripción
Este repositorio contiene la implementación del Laboratorio 2, el cual aborda la simulación del problema de los N-cuerpos (N-Body Simulation). El proyecto incluye tanto una implementación secuencial en **CPU** como una versión altamente paralelizada en **GPU** utilizando **CUDA**, permitiendo evaluar la ganancia de rendimiento (speedup) y la escalabilidad del sistema.

## Estructura del Proyecto
El código está organizado de manera modular para separar la lógica física, la gestión de memoria y la aceleración en hardware:

* `main.cpp`, `NBodySimulator.cpp`, `Integrator.cpp`: Lógica principal y orquestación de la simulación.
* `kernels/`: Directorio principal de aceleración CUDA (`accelerations.cu`, `energy.cu`).
* `CudaBuffer.h`, `CudaDeviceSoA.h`: Gestión de memoria y estructuras de datos (*Struct of Arrays*) optimizadas para GPU.
* `tests/`: Batería de pruebas unitarias y de validación física (`test_physics.cpp`, `test_cuda_buffer.cpp`, `test_gpu_equivalence.cpp`).
* `aws/`: Scripts de despliegue y definición de trabajos en Amazon Web Services (AWS Batch).
* `plot_performance.py`, `plot_gpu_benchmarks.py`: Utilidades en Python para generar las gráficas de rendimiento.
* Archivos `.slurm` y `.sh`: Scripts de ejecución para entornos clúster (SLURM) e instancias locales (`run_gpu_diinf.sh`, `run_cluster.slurm`, etc.).

## Compilación
Asegúrese de contar con los siguientes requerimientos:
* Compilador de C++ compatible con C++11/14 o superior.
* NVIDIA CUDA Toolkit.
* Make.
* Python 3 y Matplotlib (opcional, para la visualización de resultados).

Para compilar todo el proyecto, utilice el `Makefile` incluido en la raíz del repositorio:
```bash
make
```
*Nota: Si requiere limpiar los binarios u objetos intermedios, ejecute `make clean`.*

## Ejecución
### Entorno Local / Nodo Único
Puede lanzar el simulador invocando directamente el binario generado:
```bash
./nbody_sim [argumentos/flags]
```

### Entorno Clúster (SLURM)
Para enviar los trabajos de GPU a la cola del clúster (por ejemplo, para los barridos de rendimiento), utilice los scripts provistos:
```bash
sbatch run_cluster.slurm
# o bien
./run_gpu_diinf.sh
```

## Pruebas y Validación
El sistema cuenta con un arnés de pruebas (*harness*) para garantizar que los cálculos de las fuerzas e interacciones en la GPU sean matemáticamente equivalentes a los calculados por la CPU, y que la energía del sistema se conserve adecuadamente.

Puede ejecutar las pruebas construyendo los binarios de la carpeta `tests/`:
```bash
# Revisar la regla específica en el Makefile si existe (ej. make test)
./tests/test_gpu_equivalence
```

## Equipo y Roles
| Miembro        | Rol / Contribucion                        |
|----------------|-------------------------------------------|
| **Benjamín Bustamante**   | Host/device y memoria R2 |
| **Ignacio Solar**   | Kernels CUDA R1 |
| **Fabián Lizama**   | Git, releases y agentes R4 |
| **Benjamín Sepúlveda**   | Integración y validación R3 |
| **Josepha Gaete**   | Calidad, CI y visualizacion R5 |
