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
};

#endif