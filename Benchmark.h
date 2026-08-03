#ifndef BENCHMARK_H
#define BENCHMARK_H

#include <vector>
#include <functional>

struct BenchmarkResult {
    int threads;
    double mean_time;
    double std_dev;
    double speedup;
    double speedup_err;
    double efficiency;
    double efficiency_err;
    double serial_fraction;
};

// benchmark GPU (kernel-only o end-to-end) para un punto (n_bodies, variant, block_size) 
struct GpuBenchmarkResult {
    int n_bodies = 0;
    int variant = 0;
    int block_size = 0;
    double mean_time = 0.0;
    double std_dev = 0.0;
};

// comparacion CPU (SoA, baseline Lab 1) vs GPU end-to-end para un mismo N
struct CpuGpuComparison {
    int n_bodies = 0;
    double cpu_mean = 0.0;
    double cpu_std = 0.0;
    double gpu_mean = 0.0;
    double gpu_std = 0.0;
    double speedup = 0.0;
    double speedup_err = 0.0;
};

class Benchmark {
private:
    int repetitions;

public:
    Benchmark(int reps = 10) : repetitions(reps) {}

    // Ejecuta una función 'reps' veces y devuelve promedio y desviación estándar
    std::pair<double, double> measureExecutionTime(std::function<void()> simulation_task);

    // Calcula todas las métricas de rendimiento comparando el tiempo serial vs paralelo
    BenchmarkResult calculateMetrics(int threads,
                                     std::pair<double, double> serial_stats,
                                     std::pair<double, double> parallel_stats);

    // ---- benchmarks GPU - lab 2 ----
    GpuBenchmarkResult benchmarkKernelOnly(int n_bodies, int variant, int block_size,
                                           unsigned int seed = 42,
                                           double G = 1.0, double epsilon = 0.1);

    // H2D + kernel + D2H
    GpuBenchmarkResult benchmarkEndToEnd(int n_bodies, int variant, int block_size,
                                         unsigned int seed = 42,
                                         double G = 1.0, double epsilon = 0.1);

    // comparacion CPU serial (SoA, baseline Lab 1) vs GPU end-to-end para el mismo N
    CpuGpuComparison compareCpuGpu(int n_bodies, int variant = 0, int block_size = 256,
                                   unsigned int seed = 42,
                                   double G = 1.0, double epsilon = 0.1);
};

#endif