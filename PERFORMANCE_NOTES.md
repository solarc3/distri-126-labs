# Notas de rendimiento: version final SoA

Esta version del proyecto deja solo el kernel de fuerzas **SoA** (`Structure of Arrays`), porque fue el kernel que mejor rindio en las pruebas realizadas en la `c7a.48xlarge`.

Se eliminaron los kernels alternativos reales (`classic`, `newton` y la variante `collapse(2)` con atomics). La interfaz de benchmark se mantiene compatible: `computeAccelerations()`, `computeAccelerations(int)` y `computeAccelerations(int, int)` siguen existiendo porque los benchmarks de schedules/chunks las usan, pero ahora todas ejecutan la misma implementacion SoA.

## Kernel utilizado

El calculo de fuerzas se hace en `NBodySimulator::computeAccelerationsSoAImpl(...)`.

La simulacion mantiene el estado fisico en `std::vector<Particle>` para no cambiar la logica del resto del programa. Antes de calcular fuerzas, se copian los campos usados por el kernel a arreglos SoA alineados a 64 bytes:

```cpp
soa_x[i]    = particles[i].x;
soa_y[i]    = particles[i].y;
soa_mass[i] = particles[i].mass;
```

Luego el kernel trabaja sobre memoria contigua:

```cpp
x[0], x[1], x[2], ...
y[0], y[1], y[2], ...
m[0], m[1], m[2], ...
```

Esto ayuda a SIMD porque el compilador puede vectorizar el loop interno `j` con cargas consecutivas en memoria.

## Paralelismo usado

La distribucion del trabajo es:

```text
OpenMP threads -> reparten bloques de particulas i
SIMD/AVX       -> procesa varias particulas j dentro de cada core
```

La forma conceptual es:

```cpp
#pragma omp parallel
{
    #pragma omp for schedule(runtime)
    for (int ib = 0; ib < n; ib += SOA_I_TILE) {
        for (int jb = 0; jb < n; jb += SOA_J_TILE) {
            // loop interno vectorizable sobre j
        }
    }
}
```

Cada thread calcula aceleraciones para particulas `i` distintas. Por eso no hay `atomic` ni `critical` en el loop de fuerzas.

## Vectorizacion

El loop caliente tiene esta forma:

```cpp
#pragma omp simd aligned(x, y, mass:64) reduction(+:ax_local, ay_local)
for (int j = jb; j < j_end; ++j) {
    const double dx = x[j] - xi;
    const double dy = y[j] - yi;
    const double distSq = dx * dx + dy * dy + eps2;
    const double invDist = 1.0 / std::sqrt(distSq);
    const double invDist3 = invDist * invDist * invDist;
    const double a_mag = g * mass[j] * invDist3;

    ax_local += a_mag * dx;
    ay_local += a_mag * dy;
}
```

Detalles importantes:

- `x`, `y` y `mass` son arreglos contiguos.
- Estan alineados a 64 bytes mediante `AlignedAllocator`.
- `ax_local` y `ay_local` son reducciones explicitas.
- No hay escrituras compartidas dentro del loop `j`.
- Con `epsilon > 0`, la auto-interaccion `i == j` no necesita rama: `dx = dy = 0`, por lo que aporta cero aceleracion y el softening evita division por cero.

En una CPU con AVX-512, un vector de 512 bits puede contener 8 `double`. El objetivo del layout SoA es que el compilador pueda emitir instrucciones vectoriales sobre esos 8 elementos contiguos.

## Cache blocking

El kernel usa dos constantes configurables:

```cpp
SOA_I_TILE = 8
SOA_J_TILE = 4096
```

Con el default:

```text
x[j]    4096 * 8 bytes
y[j]    4096 * 8 bytes
mass[j] 4096 * 8 bytes
---------------------------
        98304 bytes = 96 KiB
```

La idea es reutilizar un bloque de `j` para varias particulas `i` antes de pasar al siguiente bloque. No busca que todo el problema entre en cache, sino mejorar reutilizacion local y reducir trafico innecesario.

Se puede experimentar recompilando con:

```bash
make clean
make EXTRA_CXXFLAGS="-DNBODY_SOA_J_TILE=2048 -DNBODY_SOA_I_TILE=8"
```

## False sharing

El hot path de fuerzas evita false sharing porque cada thread escribe aceleraciones de particulas `i` distintas y no hay acumulaciones compartidas. Ademas, `Particle` esta alineado a 64 bytes:

```cpp
class alignas(64) Particle { ... };
static_assert(sizeof(Particle) == 64);
```

Esto evita que dos particulas distintas compartan la misma linea de cache al escribir `ax` y `ay`. El costo es que el layout AoS ocupa mas memoria por particula, pero el kernel de fuerzas lee `x/y/mass` desde SoA para no pagar ese stride en el loop interno.

## Afinidad OpenMP

En las pruebas gano:

```bash
OMP_PROC_BIND=spread
OMP_PLACES=cores
OMP_NUM_THREADS=192
```

`spread` distribuye los threads por los cores disponibles. Para este workload ayudo mas que concentrarlos (`close`), probablemente porque el problema grande se beneficia de usar mejor el ancho de banda y los dominios de memoria/cache de la maquina.

## Resultados usados para el informe

| N / carpeta | mejor tiempo | mejor threads |
|---:|---:|---:|
| 1k | 0.000378 s | 8 |
| 5k | 0.001522 s | 32 |
| 10k | 0.003154 s | 64 |
| 25k | 0.008522 s | 128 |
| 50k | 0.021200 s | 192 |
| 100k | 0.068001 s | 192 |
| 250k | 0.358873 s | 192 |
| 500k | 1.419470 s | 192 |
| 500k-s2 | 2.841460 s | 192 |
| 750k-s2 | 6.440680 s | 192 |
| 1m-s2 | 11.540900 s | 192 |
| 1.5m-s1 | 13.494300 s | 192 |
| 3m-s1 | 57.810800 s | 192 |
| 5m-s1 | 163.137000 s | 192 |
| 10m-s1 | 656.635000 s | 192 |

Para los casos con `steps=2`, el tiempo por step es aproximadamente:

| caso | tiempo por step |
|---:|---:|
| 500k-s2 | 1.420730 s/step |
| 750k-s2 | 3.220340 s/step |
| 1m-s2 | 5.770450 s/step |

El mayor caso valido fue:

```text
10M cuerpos, 192 threads, steps=1: 656.635 s (~10.94 min)
```

Los casos de 15M y 20M fallaron por timeout de 20 minutos.

## Lectura de la escala observada

Entre 5M y 10M:

```text
5M  -> 163.1 s
10M -> 656.6 s
```

Al duplicar `N`, el tiempo crece aproximadamente 4x. Eso es coherente con el costo `O(N^2)` del calculo directo de N-cuerpos: duplicar cuerpos multiplica por cuatro la cantidad de interacciones.

## Comandos utiles

Compilacion para la VM objetivo:

```bash
make clean
make MARCH_FLAGS="-march=native" OPT_FLAGS="-O3 -fno-math-errno"
```

Ejecucion recomendada:

```bash
OMP_NUM_THREADS=192 \
OMP_PROC_BIND=spread \
OMP_PLACES=cores \
./nbody_sim --benchmark --force-mode soa --bodies 500000 --steps 1 --threads 192
```

Reporte de vectorizacion:

```bash
make vec-report MARCH_FLAGS="-march=native"
```

Inspeccion rapida de instrucciones vectoriales:

```bash
objdump -d -Mintel ./nbody_sim | grep -E "zmm|ymm|vsqrtpd|vdivpd|vgather|vfmadd"
```

Profiling general:

```bash
perf stat -d ./nbody_sim --benchmark --force-mode soa --bodies 100000 --steps 1 --threads 192
perf record -g -- ./nbody_sim --benchmark --force-mode soa --bodies 100000 --steps 1 --threads 192
perf report
```
