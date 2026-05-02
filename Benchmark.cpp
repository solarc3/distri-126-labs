#include "Benchmark.h"
#include <cmath>
#include <omp.h>
#include <numeric>

std::pair<double, double> Benchmark::measureExecutionTime(std::function<void()> simulation_task) {
    std::vector<double> times(repetitions);

    for (int i = 0; i < repetitions; ++i) {
        double start = omp_get_wtime();
        simulation_task();
        double end = omp_get_wtime();
        times[i] = end - start;
    }

    // Calcular promedio
    double sum = std::accumulate(times.begin(), times.end(), 0.0);
    double mean = sum / repetitions;

    // Calcular desviación estándar
    double sq_sum = 0.0;
    for (double t : times) {
        sq_sum += (t - mean) * (t - mean);
    }
    double std_dev = std::sqrt(sq_sum / repetitions);

    return {mean, std_dev};
}

BenchmarkResult Benchmark::calculateMetrics(int threads, 
                                            std::pair<double, double> serial_stats, 
                                            std::pair<double, double> parallel_stats) {
    BenchmarkResult res;
    res.threads = threads;
    res.mean_time = parallel_stats.first;
    res.std_dev = parallel_stats.second;

    double T1 = serial_stats.first;
    double dT1 = serial_stats.second;
    double Tp = parallel_stats.first;
    double dTp = parallel_stats.second;

    // Speedup y su propagación de error
    res.speedup = T1 / Tp;
    double rel_err_T1 = dT1 / T1;
    double rel_err_Tp = dTp / Tp;
    res.speedup_err = res.speedup * std::sqrt(rel_err_T1 * rel_err_T1 + rel_err_Tp * rel_err_Tp);

    // Eficiencia y su propagación de error
    res.efficiency = res.speedup / threads;
    res.efficiency_err = res.speedup_err / threads;

    // Fracción serial empírica (Ley de Amdahl)
    if (threads > 1) {
        res.serial_fraction = ((1.0 / res.speedup) - (1.0 / threads)) / (1.0 - (1.0 / threads));
    } else {
        res.serial_fraction = 1.0;
    }

    return res;
}