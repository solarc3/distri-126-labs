# Notas de paralelismo, SIMD y cache

Este documento resume los cambios hechos y la logica de rendimiento detras del codigo. La idea general es separar dos problemas distintos:

1. **Paralelismo entre nucleos**: repartir particulas entre hilos con OpenMP sin carreras, sin locks y con buen binding NUMA.
2. **Paralelismo vectorial dentro de cada nucleo**: hacer que el compilador genere instrucciones SIMD para el bucle interno de interacciones.

La version optimizada por defecto en `main.cpp` ahora usa `--force-mode soa`, porque el calculo de fuerzas es el costo dominante y la estructura SoA permite cargas contiguas y SIMD mucho mas limpio que la estructura AoS `Particle`.

---

## 1. Modelo mental del calculo N-body

Para cada particula `i` se calcula la aceleracion acumulando el efecto de todas las particulas `j`:

```cpp
dx = x[j] - x[i]
dy = y[j] - y[i]
distSq = dx*dx + dy*dy + epsilon*epsilon
invDist = 1 / sqrt(distSq)
invDist3 = invDist * invDist * invDist
a += G * mass[j] * invDist3 * (dx, dy)
```

Complejidad:

- `classic` y `soa`: `n * n` interacciones.
- `newton`: `n * (n - 1) / 2` pares, pero necesita una estrategia especial porque cada par aporta a dos particulas.

En cargas grandes, el bucle interno `j` domina todo. Por eso los cambios se concentran en que ese bucle sea:

- branch-free cuando sea posible,
- vectorizable,
- con lecturas contiguas,
- sin atomics,
- con acumuladores privados por hilo.

---

## 2. Cambios principales realizados

### 2.1 `AlignedAllocator.h` y buffers alineados a 64 bytes

Se agrego un allocator C++17 para que los vectores de `double` usados por SoA y Newton comiencen en direcciones alineadas a 64 bytes.

Por que importa:

- 64 bytes es el tamano tipico de linea de cache en x86 moderno.
- AVX-512 procesa 512 bits por vector, es decir 64 bytes por instruccion vectorial de `double`: 8 doubles por vector.
- La clausula OpenMP `aligned(ptr:64)` solo es correcta si el puntero realmente esta alineado.
- La alineacion no garantiza rendimiento por si sola, pero evita penalizaciones y le da informacion al compilador.

Archivos:

- `AlignedAllocator.h`
- `NBodyConfig.h`
- `NBodySimulator.h`

### 2.2 `NBodyConfig.h`

Centraliza constantes ajustables:

```cpp
CACHE_LINE_BYTES = 64
SOA_I_TILE = 8
SOA_J_TILE = 4096
NEWTON_CHUNK = 8
```

Se pueden cambiar al compilar:

```bash
make clean && make EXTRA_CXXFLAGS="-DNBODY_SOA_J_TILE=8192 -DNBODY_SOA_I_TILE=8"
```

### 2.3 `Particle` sigue siendo `alignas(64)` y `sizeof(Particle)==64`

Se mantuvo `Particle` en una linea de cache completa. Esto protege contra false sharing cuando varios hilos actualizan particulas adyacentes.

Trade-off importante:

- Ventaja: si el hilo A escribe `particles[i]` y el hilo B escribe `particles[i+1]`, no comparten linea de cache.
- Desventaja: el calculo de fuerza solo necesita `x`, `y`, `mass`, pero cada particula ocupa 64 bytes. En AoS se trae mucha informacion que no se usa en el bucle interno.

Por eso no se intento hacer que AoS sea el layout rapido. En cambio se agrego un camino SoA rapido.

### 2.4 `setParticles()` con first-touch paralelo

Se agrego:

```cpp
void NBodySimulator::setParticles(const std::vector<Particle>& source);
```

Esta copia en paralelo cuando `n > 2048`. El objetivo no es solo copiar mas rapido, sino hacer **first-touch NUMA**: las paginas de memoria del vector destino se asignan en el nodo NUMA del hilo que las toca primero. En una instancia grande con dos dominios NUMA esto evita que todo el arreglo quede fisicamente en la memoria cercana a un solo nucleo.

---

## 3. Implementacion `classic`

Metodo:

```cpp
computeAccelerations()
computeAccelerations(int schedule_type)
computeAccelerations(int schedule_type, int chunk_size)
```

### Antes

El bucle interno tenia:

```cpp
if (eps2 == 0.0 && i == j) continue;
```

Ese `if` esta dentro del bucle mas caliente. Aunque normalmente `epsilon > 0`, el compilador ve una rama dependiente de `i` y `j`, y eso dificulta vectorizar.

### Ahora

Se separan dos caminos:

1. `eps2 > 0`: no se salta `j == i`, porque `dx == dy == 0` y el aporte es cero. El bucle queda sin rama.
2. `eps2 == 0`: se parte el bucle en `[0, i)` y `(i, n)`, evitando la singularidad sin meter `if` en el bucle SIMD.

Fragmento conceptual:

```cpp
if (eps2 > 0.0) {
    #pragma omp simd reduction(+:ax_local, ay_local)
    for (int j = 0; j < n; ++j) { ... }
} else {
    #pragma omp simd reduction(+:ax_local, ay_local)
    for (int j = 0; j < i; ++j) { ... }

    #pragma omp simd reduction(+:ax_local, ay_local)
    for (int j = i + 1; j < n; ++j) { ... }
}
```

### Seguridad paralela

El paralelismo externo es por `i`:

```cpp
#pragma omp parallel for schedule(static)
for (int i = 0; i < n; ++i) { ... }
```

Cada hilo escribe solamente:

```cpp
particles[i].ax
particles[i].ay
```

No hay dos hilos escribiendo la misma particula, por lo tanto no hacen falta `atomic`, `critical` ni locks.

### Schedules

- `static`: mejor default para classic/SoA, porque cada `i` hace casi el mismo trabajo (`n` interacciones).
- `dynamic`: mas overhead; util para experimentos o trabajo irregular.
- `guided`: reduce overhead respecto de dynamic, pero tampoco es necesario en classic.

La version con `chunk_size` sigue disponible para benchmark.

---

## 4. Implementacion `soa`

Metodo:

```cpp
computeAccelerationsSoA()
```

### Idea

`Particle` es AoS:

```cpp
[x y vx vy ax ay mass padding] [x y vx vy ax ay mass padding] ...
```

El bucle de fuerza necesita leer `x[j]`, `y[j]`, `mass[j]` para muchos `j`. En AoS esas lecturas tienen stride de 64 bytes. Eso es malo para cache y malo para SIMD.

SoA crea buffers contiguos:

```cpp
soa_x[j]
soa_y[j]
soa_mass[j]
```

Ahora el bucle interno lee memoria contigua:

```cpp
const double dx = x[j] - xi;
const double dy = y[j] - yi;
const double a_mag = g * mass[j] * invDist3;
```

### Cache blocking

La nueva version procesa bloques de `i` y bloques de `j`:

```cpp
for ib in bloques de SOA_I_TILE:
    ax_tile[SOA_I_TILE] = 0
    ay_tile[SOA_I_TILE] = 0

    for jb in bloques de SOA_J_TILE:
        for ii in particulas del bloque i:
            #pragma omp simd reduction(+:ax_local, ay_local)
            for j in bloque j:
                acumular interaccion
```

Defaults:

- `SOA_I_TILE = 8`
- `SOA_J_TILE = 4096`

El bloque `j` ocupa aproximadamente:

```text
3 arrays * 4096 doubles * 8 bytes = 98,304 bytes ~= 96 KiB
```

Ese tamano busca reutilizar `x/y/mass` desde cache privada mientras se calcula para varias particulas `i`. Si un caso real muestra otro comportamiento, cambiar `NBODY_SOA_J_TILE` es facil.

### Por que SoA es el default

Es el camino mas amigable para AVX2/AVX-512:

- cargas contiguas,
- reducciones claras,
- punteros alineados,
- menos gather/scatter,
- menos bytes inutiles traidos desde memoria.

En `main.cpp`, `force_mode` ahora parte como `soa`, aunque se puede cambiar con:

```bash
./nbody_sim --force-mode classic
./nbody_sim --force-mode newton
./nbody_sim --force-mode soa
```

---

## 5. Implementacion `newton`

Metodo:

```cpp
computeAccelerationsNewton3()
```

### Que hace

Usa la tercera ley de Newton: el par `(i, j)` se calcula una sola vez.

Para cada par:

```cpp
ai += +G * m[j] * r_ij / |r|^3
aj += -G * m[i] * r_ij / |r|^3
```

Esto reduce casi a la mitad el numero de interacciones aritmeticas.

### Por que es mas dificil paralelizar

En classic/SoA, cada hilo escribe una unica salida `i`. En Newton, cada par actualiza dos particulas: `i` y `j`. Si muchos hilos actualizan `j`, aparecen carreras.

Soluciones posibles:

1. `atomic` por actualizacion: simple pero muy lento.
2. Locks por particula: menos simple y sigue siendo caro.
3. Buffers privados por hilo: mas memoria, pero sin locks en el bucle caliente.

Se eligio la opcion 3.

### Layout de buffers

```cpp
newton_ax_buffer[thread][particle]
newton_ay_buffer[thread][particle]
```

Cada hilo escribe solo su fila. Luego se hace una reduccion final:

```cpp
particles[i].ax = sum_t newton_ax_buffer[t][i]
particles[i].ay = sum_t newton_ay_buffer[t][i]
```

### Cambio importante: padding por fila

Antes la fila era de tamano exacto `n`. Si `n * sizeof(double)` no era multiplo de 64, el final de la fila de un hilo podia compartir linea de cache con el inicio de la fila del hilo siguiente. Eso es false sharing de borde.

Ahora:

```cpp
newton_row_stride = round_up_to_cache_line_doubles(n)
```

Cada fila comienza en una linea de cache.

### Cambio importante: zeroing dentro de la region paralela

Antes se hacia `std::fill()` fuera de la region paralela. En NUMA, eso puede colocar todas las paginas del buffer en un solo nodo.

Ahora cada hilo limpia su propia fila:

```cpp
#pragma omp parallel
{
    tid = omp_get_thread_num();
    ax = base + tid * stride;
    ay = base + tid * stride;
    std::fill(ax, ax + n, 0.0);
    std::fill(ay, ay + n, 0.0);
    ... calcular pares asignados a este hilo ...
}
```

Eso mejora first-touch y evita trafico remoto innecesario.

### Memoria de Newton

Costo aproximado:

```text
2 buffers * threads * n * 8 bytes
```

Ejemplos con 192 hilos:

```text
n = 10,000   -> ~30.7 MiB
n = 100,000  -> ~307 MiB
n = 1,000,000 -> ~3.07 GiB
```

Newton puede ser excelente para `n` mediano/grande si la memoria extra cabe bien. Para casos enormes, SoA puede ser mas estable porque no multiplica memoria por numero de hilos.

---

## 6. SIMD, AVX-512 y que hace el compilador

### Que es SIMD

SIMD significa Single Instruction, Multiple Data. Una instruccion opera sobre varias lanes.

En double precision:

```text
SSE 128-bit   -> 2 doubles
AVX2 256-bit  -> 4 doubles
AVX-512       -> 8 doubles
```

Un bucle como:

```cpp
for (int j = 0; j < n; ++j) {
    ax += f(x[j], y[j], mass[j]);
}
```

puede convertirse en algo conceptualmente parecido a:

```text
cargar 8 x[j]
cargar 8 y[j]
cargar 8 mass[j]
calcular 8 dx, 8 dy, 8 sqrt, 8 divisiones
acumular 8 contribuciones
reducir las 8 lanes a un escalar final
```

### Que aportan AVX-512 y VNNI

Para este codigo, lo relevante de AVX-512 es el ancho vectorial y las mascaras. VNNI y bfloat16 son mas importantes para inferencia/IA; no son el cuello de botella de esta simulacion en `double`.

AVX-512 permite:

- 8 doubles por vector,
- instrucciones vectoriales de `sqrt` y division,
- mascaras para tails o ramas simples,
- mas registros vectoriales (`zmm`) que ayudan a mantener acumuladores.

Pero AVX-512 no arregla automaticamente un layout malo. Si los datos estan en AoS con stride 64, el compilador puede necesitar gathers. SoA ayuda mucho mas que simplemente pedir `-march=native`.

### Cuando el compilador puede vectorizar

Le gustan bucles con estas propiedades:

- contador simple (`for j = 0; j < n; ++j`),
- memoria contigua o patron predecible,
- sin llamadas con efectos laterales,
- sin ramas complejas,
- sin alias ambiguo entre punteros,
- sin dependencias loop-carried reales,
- reducciones explicitas.

Por eso se agregaron:

```cpp
#pragma omp simd reduction(+:ax_local, ay_local)
#pragma omp simd aligned(x, y, mass:64)
NBODY_RESTRICT
-fno-math-errno
```

### `-fno-math-errno`

`std::sqrt` historicamente puede setear `errno`. Si el compilador debe preservar eso, trata `sqrt` como una llamada con efectos laterales y se vuelve mas conservador.

`-fno-math-errno` dice que no dependemos de `errno` para funciones matematicas. Es mucho menos agresivo que `-ffast-math`: no habilita toda la familia de transformaciones que pueden romper NaN/Inf/asociatividad de forma fuerte.

### Por que no se activo `-ffast-math` por defecto

`-ffast-math` puede acelerar, pero cambia reglas numericas:

- puede reasociar sumas,
- puede asumir que no hay NaN/Inf,
- puede cambiar resultados bit a bit,
- puede alterar tests estrictos.

Para esta app se dejo una optimizacion segura por defecto. Si quieres probarlo como benchmark experimental:

```bash
make clean && make EXTRA_CXXFLAGS="-ffast-math"
```

Compara energia, momento y estabilidad antes de adoptarlo.

---

## 7. Cache, 64 bytes y false sharing

### Cache line de 64 bytes

En x86 moderno, una linea de cache suele tener 64 bytes. Si dos hilos escriben variables distintas que caen en la misma linea, el hardware invalida la linea entre cores aunque logicamente no compartan la variable. Eso es **false sharing**.

### Donde habia riesgo

1. `Particle` adyacentes: mitigado con `alignas(64)` y `sizeof(Particle)==64`.
2. Buffers Newton por hilo: mitigado con `newton_row_stride` redondeado a linea de cache.
3. Variables globales acumuladas con `atomic`/`critical`: se mantienen solo para benchmarks, no para kernels rapidos.
4. `collapse(2)` con atomics en aceleracion: se conserva como demostracion de mala estrategia, no como camino rapido.

### Por que 64 bytes tambien puede ser problema

Padding a 64 bytes evita false sharing, pero aumenta el footprint:

```text
Particle: 64 bytes
Datos realmente usados por fuerza: x, y, mass = 24 bytes
```

Cada lectura AoS trae bastante dato inutil para el bucle de fuerza. SoA reduce eso:

```text
soa_x + soa_y + soa_mass = 24 bytes por particula
```

Esto mejora cache y memoria, especialmente al barrer `j` muchas veces.

### Regla practica

- Para estructuras que muchos hilos escriben de forma adyacente: padding/alignment puede ayudar.
- Para datos que se leen masivamente en SIMD: SoA suele ganar.
- No alinear todo por costumbre; medir.

---

## 8. c7a.48xlarge: como correr

Recomendacion base:

```bash
export OMP_NUM_THREADS=192
export OMP_PROC_BIND=spread
export OMP_PLACES=cores
export OMP_DISPLAY_ENV=TRUE

make clean && make MARCH_FLAGS="-march=native"
./nbody_sim --benchmark-all \
  --force-mode soa \
  --bodies 5000 \
  --steps 100 \
  --repetitions 5 \
  --extra-repetitions 1 \
  --threads 1,2,4,8,16,32,64,96,128,192 \
  --variant-threads 96
```

Notas:

- `spread` reparte hilos entre dominios NUMA y cores. Suele ser buen punto de partida en instancias grandes.
- Para casos que caben muy bien en L3 de un socket, prueba tambien `OMP_PROC_BIND=close` y compara.
- Siempre guardar `lscpu`, `numactl --hardware` y `OMP_DISPLAY_ENV` con los resultados.

---

## 9. Herramientas recomendadas

### Vectorizacion del compilador

```bash
make vec-report
```

Buscar lineas como:

```text
optimized: loop vectorized using 32 byte vectors
optimized: loop vectorized using 64 byte vectors
missed: not vectorized: unsupported control flow
missed: not vectorized: possible aliasing
```

Si compilas en una maquina AVX-512 real y el compilador decide usar zmm, deberias ver 64 bytes. En maquinas sin AVX-512 veras 32 bytes o menos.

### Inspeccionar instrucciones

```bash
objdump -d -Mintel nbody_sim | grep -E "zmm|ymm|vsqrtpd|vdivpd|vgather|vfmadd" | head -80
```

Indicadores:

- `zmm`: AVX-512.
- `ymm`: AVX/AVX2.
- `vsqrtpd`: sqrt vectorial double.
- `vdivpd`: division vectorial double.
- `vgather*`: gather; no siempre malo, pero suele indicar layout menos ideal.

### Perf stat

```bash
perf stat -d \
  ./nbody_sim --benchmark --force-mode soa --bodies 5000 --steps 20 --repetitions 1 --threads 192
```

Metricas utiles:

- instrucciones por ciclo,
- cache misses,
- LLC load misses,
- branch misses,
- tiempo total.

### Perf record/report

```bash
make profile
perf record -g -- ./nbody_sim --benchmark --force-mode soa --bodies 5000 --steps 20 --repetitions 1 --threads 192
perf report
```

Sirve para ver si el tiempo esta realmente en `computeAccelerationsSoA`, `sqrt`, division, runtime OpenMP, atomics, etc.

### NUMA/topologia

```bash
lscpu -e=CPU,NODE,SOCKET,CORE,CACHE
numactl --hardware
hwloc-ls
```

### Afinidad OpenMP

```bash
OMP_DISPLAY_ENV=TRUE OMP_NUM_THREADS=192 OMP_PROC_BIND=spread OMP_PLACES=cores ./nbody_sim --benchmark ...
```

Si ves migraciones o resultados muy variables, revisa binding antes de tocar el algoritmo.

---

## 10. Que evitar

- `critical` dentro del bucle de particulas: serializa.
- `atomic` por interaccion: destruye escalabilidad.
- `collapse(2)` para acumulaciones por particula sin privatizar: obliga atomics.
- `dynamic` con chunk muy pequeno cuando cada iteracion cuesta lo mismo.
- Tareas OpenMP por particula para trabajo trivial: overhead mayor que el calculo.
- AoS como layout principal para un bucle que solo lee `x/y/mass` masivamente.
- Benchmark sin binding ni metadata de CPU.
- Comparar AVX-512 compilando en una maquina que no tiene AVX-512 si usas `-march=native`.

---

## 11. Lectura rapida de modos

| Modo | Ventaja | Costo/riesgo | Uso recomendado |
|------|---------|--------------|-----------------|
| `classic` | simple, poco extra memory, race-free | AoS stride 64, peor SIMD/cache | referencia y comparacion |
| `soa` | mejor SIMD/cache, memoria extra baja | copia AoS->SoA por paso | default en c7a |
| `newton` | mitad de pares | buffers `O(n*threads)`, reduccion final, mas complejo | n mediano/grande si memoria cabe |
| `collapse` | demuestra `collapse(2)` | atomics por interaccion | solo benchmark pedagogico |

