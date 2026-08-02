#include "Benchmark.h"
#include "NBodySimulator.h"
#include <cmath>
#include <omp.h>
#include <numeric>
#include <chrono>
#include <tuple>
#include <stdexcept>

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

namespace {

std::pair<double, double> meanAndStdDev(const std::vector<double>& times) {
    if (times.empty()) {
        return {0.0, 0.0};
    }
    const double sum = std::accumulate(times.begin(), times.end(), 0.0);
    const double mean = sum / static_cast<double>(times.size());
    double sq_sum = 0.0;
    for (double t : times) {
        sq_sum += (t - mean) * (t - mean);
    }
    const double std_dev = std::sqrt(sq_sum / static_cast<double>(times.size()));
    return {mean, std_dev};
}

NBodySimulator makeGpuBenchSimulator(int n_bodies, unsigned int seed, double G, double epsilon) {
    NBodySimulator sim(G, epsilon);
    sim.initializeRandom(n_bodies, seed, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);
    return sim;
}

} 

GpuBenchmarkResult Benchmark::benchmarkKernelOnly(int n_bodies, int variant, int block_size,
                                                  unsigned int seed, double G, double epsilon) {
    GpuBenchmarkResult result;
    result.n_bodies = n_bodies;
    result.variant = variant;
    result.block_size = block_size;

    NBodySimulator sim = makeGpuBenchSimulator(n_bodies, seed, G, epsilon);

    sim.uploadGpuBuffers();

    std::vector<double> times(repetitions);
    for (int r = 0; r < repetitions; ++r) {
        const auto t0 = std::chrono::steady_clock::now();
        sim.computeAccelerationsGpuKernelOnly(variant, block_size);
        const auto t1 = std::chrono::steady_clock::now();
        times[r] = std::chrono::duration<double>(t1 - t0).count();
    }

    sim.downloadGpuAccelerations();

    std::tie(result.mean_time, result.std_dev) = meanAndStdDev(times);
    return result;
}

GpuBenchmarkResult Benchmark::benchmarkEndToEnd(int n_bodies, int variant, int block_size,
                                                unsigned int seed, double G, double epsilon) {
    GpuBenchmarkResult result;
    result.n_bodies = n_bodies;
    result.variant = variant;
    result.block_size = block_size;

    NBodySimulator sim = makeGpuBenchSimulator(n_bodies, seed, G, epsilon);

    std::vector<double> times(repetitions);
    for (int r = 0; r < repetitions; ++r) {
        const auto t0 = std::chrono::steady_clock::now();
        sim.computeAccelerationsGpu(variant, block_size);
        const auto t1 = std::chrono::steady_clock::now();
        times[r] = std::chrono::duration<double>(t1 - t0).count();
    }

    std::tie(result.mean_time, result.std_dev) = meanAndStdDev(times);
    return result;
}

CpuGpuComparison Benchmark::compareCpuGpu(int n_bodies, int variant, int block_size,
                                          unsigned int seed, double G, double epsilon) {
    CpuGpuComparison cmp;
    cmp.n_bodies = n_bodies;

    NBodySimulator cpuSim = makeGpuBenchSimulator(n_bodies, seed, G, epsilon);
    std::vector<double> cpu_times(repetitions);
    for (int r = 0; r < repetitions; ++r) {
        const auto t0 = std::chrono::steady_clock::now();
        cpuSim.computeAccelerationsSoA();
        const auto t1 = std::chrono::steady_clock::now();
        cpu_times[r] = std::chrono::duration<double>(t1 - t0).count();
    }
    std::tie(cmp.cpu_mean, cmp.cpu_std) = meanAndStdDev(cpu_times);

    const GpuBenchmarkResult gpu = benchmarkEndToEnd(n_bodies, variant, block_size, seed, G, epsilon);
    cmp.gpu_mean = gpu.mean_time;
    cmp.gpu_std = gpu.std_dev;

    if (cmp.cpu_mean <= 0.0 || cmp.gpu_mean <= 0.0) {
        throw std::runtime_error(
            "Benchmark::compareCpuGpu: tiempo medido invalido (<=0). "
            "Revisa que 'repetitions' > 0 y que el binario tenga acceso a una GPU real.");
    }

    cmp.speedup = cmp.cpu_mean / cmp.gpu_mean;
    const double rel_err_cpu = cmp.cpu_std / cmp.cpu_mean;
    const double rel_err_gpu = cmp.gpu_std / cmp.gpu_mean;
    cmp.speedup_err = cmp.speedup * std::sqrt(rel_err_cpu * rel_err_cpu + rel_err_gpu * rel_err_gpu);

    return cmp;
}