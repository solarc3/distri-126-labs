#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <omp.h>
#include <fstream>
#include <vector>
#include <random>
#include <cmath>
#include <cstdlib>
#include <exception>
#include "NBodySimulator.h"
#include "Benchmark.h"
#include "MetricsCalculator.h"
#include "Visualizer.h"

namespace {
std::vector<int> parse_int_list(const std::string& value) {
    std::vector<int> result;
    size_t start = 0;
    while (start < value.size()) {
        size_t comma = value.find(',', start);
        std::string token = value.substr(start, comma == std::string::npos ? std::string::npos : comma - start);
        if (!token.empty()) {
            result.push_back(std::stoi(token));
        }
        if (comma == std::string::npos) break;
        start = comma + 1;
    }
    return result;
}
}  // namespace

int main(int argc, char* argv[]) {
    double G = 1.0;
    double epsilon = 0.1;
    double dt = 0.01;
    int steps = 100;
    int num_particles = 2000;
    int output_every = 10;
    int repetitions = 10;
    int extra_repetitions = 3;
    std::vector<int> thread_counts = {2, 4, 8, 16};
    int variant_threads = 4;
    // El costo end-to-end en N chico esta dominado por transferencia PCIe, no por
    // computo (ver PERFORMANCE_NOTES.md); el beneficio real de multi-GPU (issue #75)
    // solo se observa desde N>=50000 aprox, donde el kernel O(N^2) empieza a dominar.
    std::vector<int> gpu_n_values = {256, 512, 1024, 2000, 50000};
    std::vector<int> gpu_block_sizes = {64, 128, 256, 512, 1024};
    std::vector<int> gpu_variants = {0, 1};

    unsigned int seed = 42;
    bool run_benchmark = false;
    bool run_benchmark_all = false;
    bool run_benchmark_gpu = false;
    bool skip_serial = false;
    double serial_time_override = -1.0;
    bool gpu_skip_cpu = false;
    std::string force_mode = "soa";
    if (const char* env_force_mode = std::getenv("NBODY_FORCE_MODE")) {
        force_mode = env_force_mode;
    }
    for (int i = 1; i < argc; ++i) {
        std::string arg(argv[i]);
        auto require_value = [&](const std::string& option) -> std::string {
            if (i + 1 >= argc) {
                std::cerr << "Error: falta valor para " << option << std::endl;
                std::exit(1);
            }
            return std::string(argv[++i]);
        };

        if (arg == "--benchmark-all" || arg == "-analysis") {
            run_benchmark = true;
            run_benchmark_all = true;
        } else if (arg == "--benchmark" || arg == "-benchmark") {
            run_benchmark = true;
        } else if (arg == "--benchmark-gpu") {
            run_benchmark_gpu = true;
        } else if (arg == "--gpu-n-values") {
            gpu_n_values = parse_int_list(require_value(arg));
        } else if (arg == "--gpu-block-sizes") {
            gpu_block_sizes = parse_int_list(require_value(arg));
        } else if (arg == "--gpu-variants") {
            gpu_variants = parse_int_list(require_value(arg));
        } else if (arg == "--skip-cpu") {
            gpu_skip_cpu = true;
        } else if (arg == "--bodies" || arg == "-n") {
            num_particles = std::stoi(require_value(arg));
        } else if (arg == "--steps") {
            steps = std::stoi(require_value(arg));
        } else if (arg == "--output-every") {
            output_every = std::stoi(require_value(arg));
        } else if (arg == "--dt") {
            dt = std::stod(require_value(arg));
        } else if (arg == "--epsilon") {
            epsilon = std::stod(require_value(arg));
        } else if (arg == "--seed") {
            seed = static_cast<unsigned int>(std::stoul(require_value(arg)));
        } else if (arg == "--repetitions") {
            repetitions = std::stoi(require_value(arg));
        } else if (arg == "--extra-repetitions") {
            extra_repetitions = std::stoi(require_value(arg));
        } else if (arg == "--variant-threads") {
            variant_threads = std::stoi(require_value(arg));
        } else if (arg == "--threads") {
            thread_counts = parse_int_list(require_value(arg));
        } else if (arg == "--skip-serial") {
            skip_serial = true;
        } else if (arg == "--serial-seconds") {
            serial_time_override = std::stod(require_value(arg));
        } else if (arg == "--force-mode") {
            force_mode = require_value(arg);
        } else if (arg == "--help" || arg == "-h") {
            std::cout << "Uso: ./nbody_sim [--benchmark|--benchmark-all|--benchmark-gpu] [opciones]\n"
                      << "Opciones:\n"
                      << "  --bodies N             Numero de cuerpos (default: 2000)\n"
                      << "  --steps N              Pasos temporales (default: 100)\n"
                      << "  --dt X                 Paso de tiempo (default: 0.01)\n"
                      << "  --epsilon X            Suavizado (default: 0.1)\n"
                      << "  --seed N               Semilla reproducible (default: 42)\n"
                      << "  --repetitions N        Repeticiones benchmark principal (default: 10)\n"
                      << "  --extra-repetitions N  Repeticiones benchmarks extra (default: 3)\n"
                      << "  --threads LISTA        Hilos a medir, separados por coma (default: 2,4,8,16)\n"
                      << "  --variant-threads N    Hilos para schedules/chunks/sync (default: 4)\n"
                      << "  --skip-serial          Saltea la medicion T=1 (usar con --serial-seconds)\n"
                      << "  --serial-seconds X     Tiempo serial pre-calculado para speedup\n"
                      << "  --force-mode M         Calculo de fuerzas disponible: soa (default: soa)\n"
                      << "  --benchmark-gpu        Matriz GPU kernel-only/end-to-end x blockDim.x (requiere build CUDA).\n"
                      << "                         Ignora --bodies/--steps; usa --gpu-n-values/--gpu-block-sizes/--gpu-variants.\n"
                      << "  --gpu-n-values LISTA   Valores de N para --benchmark-gpu, separados por coma\n"
                      << "                         (default: 256,512,1024,2000,50000).\n"
                      << "  --gpu-block-sizes LISTA  Valores de blockDim.x para --benchmark-gpu, separados por coma\n"
                      << "                         (default: 64,128,256,512,1024).\n"
                      << "  --gpu-variants LISTA   Variantes de kernel para --benchmark-gpu, separadas por coma\n"
                      << "                         (0=basica, 1=shared memory; default: 0,1).\n"
                      << "  --skip-cpu             En --benchmark-gpu, omite Benchmark::compareCpuGpu (CPU O(N^2)) por\n"
                      << "                         punto; util con N grandes donde la comparacion CPU seria muy lenta.\n";
            return 0;
        } else {
            seed = static_cast<unsigned int>(std::stoul(arg));
        }
    }

    if (num_particles <= 0 || steps <= 0 || output_every <= 0 || repetitions <= 0 ||
        extra_repetitions <= 0 || thread_counts.empty() || variant_threads <= 0 ||
        dt <= 0.0 || epsilon <= 0.0) {
        std::cerr << "Error: parametros invalidos. Use --help para ver opciones." << std::endl;
        return 1;
    }
    if (run_benchmark_gpu &&
        (gpu_n_values.empty() || gpu_block_sizes.empty() || gpu_variants.empty())) {
        std::cerr << "Error: --gpu-n-values/--gpu-block-sizes/--gpu-variants no pueden quedar vacios. "
                     "Use --help para ver opciones." << std::endl;
        return 1;
    }
    if (force_mode != "soa") {
        std::cerr << "Error: esta version limpia solo incluye --force-mode soa." << std::endl;
        return 1;
    }

    if (run_benchmark_gpu) {
#if !defined(NBODY_ENABLE_CUDA_KERNELS)
        std::cerr << "Error: este binario fue compilado sin NBODY_ENABLE_CUDA_KERNELS "
                     "(nvcc/kernels/*.cu no disponibles al momento de compilar).\n"
                  << "Recompila en una maquina con CUDA Toolkit (ver Dockerfile/Makefile) "
                     "o corre en el nodo GPU del cluster DIINF.\n";
        return 1;
#else
        std::cout << "--- Modo Benchmark GPU (matriz N x variante x blockDim.x, seccion 8.2 del enunciado) ---\n"
                  << "Repeticiones por punto: " << repetitions << " | semilla: " << seed << "\n"
                  << "N: " << gpu_n_values.size() << " valores | variantes: " << gpu_variants.size()
                  << " | blockDim.x: " << gpu_block_sizes.size() << " valores\n"
                  << "NOTA: variant=1 (shared memory) todavia ejecuta el kernel basico por dentro "
                     "hasta que se integre el kernel shared (issue #20); los tiempos se actualizaran cuando eso ocurra.\n\n";

        const int cpu_gpu_block_size = 256;

        try {
            Benchmark gpu_bench(repetitions);

            std::ofstream blockdim_file("blockdim_study.dat");
            if (!blockdim_file.is_open()) {
                std::cerr << "Error: no se pudo abrir 'blockdim_study.dat' para escritura.\n"
                          << "Verifica permisos de escritura en el directorio de trabajo.\n";
                return 1;
            }
            blockdim_file << "# N\tvariant\tblock_size\tkernel_mean_s\tkernel_std_s\tend2end_mean_s\tend2end_std_s\n";

            std::ofstream gpu_results_file("gpu_benchmark_results.dat");
            if (!gpu_results_file.is_open()) {
                std::cerr << "Error: no se pudo abrir 'gpu_benchmark_results.dat' para escritura.\n"
                          << "Verifica permisos de escritura en el directorio de trabajo.\n";
                return 1;
            }
            gpu_results_file << "# N\tvariant\tblock_size\tcpu_mean_s\tcpu_std_s\tgpu_mean_s\tgpu_std_s\tspeedup\tspeedup_err\n";

            for (int n : gpu_n_values) {
                for (int variant : gpu_variants) {
                    for (int block_size : gpu_block_sizes) {
                        GpuBenchmarkResult kernel_only =
                            gpu_bench.benchmarkKernelOnly(n, variant, block_size, seed, G, epsilon);
                        GpuBenchmarkResult end_to_end =
                            gpu_bench.benchmarkEndToEnd(n, variant, block_size, seed, G, epsilon);

                        blockdim_file << n << "\t" << variant << "\t" << block_size << "\t"
                                      << kernel_only.mean_time << "\t" << kernel_only.std_dev << "\t"
                                      << end_to_end.mean_time << "\t" << end_to_end.std_dev << "\n";
                        blockdim_file.flush();

                        std::cout << "  N=" << n << " variant=" << variant << " block=" << block_size
                                  << "  kernel-only=" << kernel_only.mean_time << "s"
                                  << "  end-to-end=" << end_to_end.mean_time << "s\n";
                        std::cout.flush();
                    }

                    if (!gpu_skip_cpu) {
                        CpuGpuComparison cmp =
                            gpu_bench.compareCpuGpu(n, variant, cpu_gpu_block_size, seed, G, epsilon);
                        gpu_results_file << n << "\t" << variant << "\t" << cpu_gpu_block_size << "\t"
                                          << cmp.cpu_mean << "\t" << cmp.cpu_std << "\t"
                                          << cmp.gpu_mean << "\t" << cmp.gpu_std << "\t"
                                          << cmp.speedup << "\t" << cmp.speedup_err << "\n";
                        gpu_results_file.flush();
                    }
                }
            }

            std::cout << "\nBenchmark GPU completado. Datos en 'blockdim_study.dat' y 'gpu_benchmark_results.dat'.\n"
                      << "importante: para el reporte final esta matriz debe correrse en el nodo GPU del "
                         "cluster DIINF (ver README > Benchmarks GPU).\n";
        } catch (const std::exception& e) {
            std::cerr << "\nError ejecutando el benchmark GPU: " << e.what() << "\n"
                      << "Esto normalmente significa que no hay una GPU NVIDIA real disponible en esta "
                         "maquina/contenedor (revisa 'nvidia-smi' y, en Docker, que se haya usado --gpus all).\n"
                         "--benchmark-gpu solo produce datos validos en una maquina con GPU, "
                         "p.ej. el nodo GPU del cluster DIINF.\n";
            return 1;
        }
        return 0;
#endif
    }

    auto compute_forces = [&](NBodySimulator& sim) {
        sim.computeAccelerationsSoA();
    };

    std::vector<Particle> initial_particles;
    initial_particles.reserve(static_cast<std::size_t>(num_particles));
    std::mt19937 gen(seed);
    std::uniform_real_distribution<double> pos_dist(-10.0, 10.0);
    std::uniform_real_distribution<double> vel_dist(-1.0, 1.0);
    std::uniform_real_distribution<double> mass_dist(0.5, 2.0);

    for (int i = 0; i < num_particles; ++i) {
        initial_particles.push_back(Particle(pos_dist(gen), pos_dist(gen),
                                             vel_dist(gen), vel_dist(gen), mass_dist(gen)));
    }

    if (!run_benchmark) {
        std::cout << "--- Modo Fisica (" << num_particles << " particulas) ---" << std::endl;
        std::cout << "Semilla: " << seed << std::endl;

        double t_serial_start = omp_get_wtime();
        NBodySimulator sim(G, epsilon);
        sim.setParticles(initial_particles);
        double t_serial_end = omp_get_wtime();

        std::ofstream metrics_file("energy_timeseries.dat");
        metrics_file << "Step\tKinetic\tPotential\tTotal\tPx\tPy\tCMx\tCMy\tRMS_Radius\tMinDist\tPMag\n";

        double start = omp_get_wtime();
        for (int step = 0; step < steps; ++step) {
            compute_forces(sim);
            sim.integrate(dt);

            if (step % output_every == 0) {
                std::ostringstream name;
                name << "state_" << std::setw(4) << std::setfill('0') << step << ".dat";
                Visualizer::exportState(sim, name.str());

                double kin, pot;
                sim.calculateEnergy(kin, pot);

                const auto& particles = sim.getParticles();

                auto P = MetricsCalculator::calculateTotalMomentum(particles);
                double p_mag = std::sqrt(P.first * P.first + P.second * P.second); // Nueva magnitud
                auto CM = MetricsCalculator::calculateCenterOfMass(particles);
                double rms = MetricsCalculator::calculateRMSRadius(particles);
                double min_dist = MetricsCalculator::calculateMinDistance(particles);

                metrics_file << step << "\t" << kin << "\t" << pot << "\t" << (kin + pot) << "\t"
                            << P.first << "\t" << P.second << "\t"
                            << CM.first << "\t" << CM.second << "\t"
                            << rms << "\t" << min_dist << "\t" << p_mag << "\n";

                std::cout << "Paso " << step << " procesado y registrado..." << std::endl;
            }
        }
        metrics_file.close();
        double end = omp_get_wtime();
        
        std::cout << "\n--- INSTRUMENTACION EXPLICITA (Fraccion Serial Empirica) ---" << std::endl;
        double t_serial = t_serial_end - t_serial_start;
        double t_parallel = end - start;
        double t_total = t_serial + t_parallel;
        
        std::cout << "Tiempo puramente serial (Inicializacion): " << t_serial << " s" << std::endl;
        std::cout << "Tiempo paralelo (Bucle de fisica): " << t_parallel << " s" << std::endl;
        std::cout << "Tiempo total: " << t_total << " s" << std::endl;
        std::cout << "Fraccion serial medida: " << (t_serial / t_total) * 100.0 << " %" << std::endl;
        
        std::cout << "\nMetricas guardadas exitosamente en 'energy_timeseries.dat'" << std::endl;

        std::cout << "\n--- Verificacion de sobrecargas OpenMP ---" << std::endl;
        {
            const int VN = 100;
            std::vector<Particle> vp;
            std::mt19937 vgen(99);
            for (int i = 0; i < VN; ++i)
                vp.emplace_back(pos_dist(vgen), pos_dist(vgen), vel_dist(vgen), vel_dist(vgen), mass_dist(vgen));

            auto make_vsim = [&]() {
                NBodySimulator s(G, epsilon);
                s.setParticles(vp);
                return s;
            };

            for (int s = 0; s <= 2; ++s) {
                auto sim = make_vsim();
                sim.computeAccelerations(s);
                bool ok = true;
                for (const auto& p : sim.getParticles())
                    if (!std::isfinite(p.getAx()) || !std::isfinite(p.getAy())) { ok = false; break; }
                std::cout << "  computeAccelerations(schedule=" << s << "): " << (ok ? "OK" : "FAIL") << std::endl;
            }

            for (int s = 0; s <= 2; ++s) {
                auto sim = make_vsim();
                sim.computeAccelerations(s, 25);
                bool ok = true;
                for (const auto& p : sim.getParticles())
                    if (!std::isfinite(p.getAx()) || !std::isfinite(p.getAy())) { ok = false; break; }
                std::cout << "  computeAccelerations(schedule=" << s << ", chunk=25): " << (ok ? "OK" : "FAIL") << std::endl;
            }

            const char* snames[] = {"ATOMIC", "CRITICAL", "NOWAIT", "NORMAL"};
            for (int sy = 0; sy <= 3; ++sy) {
                auto sim = make_vsim();
                sim.computeAccelerations();
                sim.integrateEuler(dt, sy);
                bool ok = true;
                for (const auto& p : sim.getParticles())
                    if (!std::isfinite(p.getX()) || !std::isfinite(p.getY())) { ok = false; break; }
                std::cout << "  integrateEuler(" << snames[sy] << "): " << (ok ? "OK" : "FAIL") << std::endl;
            }

            {
                auto sim = make_vsim();
                sim.computeAccelerations();
                sim.integrateEuler(dt, 2, true);
                bool ok = true;
                for (const auto& p : sim.getParticles())
                    if (!std::isfinite(p.getX()) || !std::isfinite(p.getY())) { ok = false; break; }
                std::cout << "  integrateEuler(NOWAIT+barrier): " << (ok ? "OK" : "FAIL") << std::endl;
            }

            {
                auto sim = make_vsim();
                sim.computeAccelerations();
                double k0, p0, k1, p1, k2, p2, k3, p3;
                sim.calculateEnergy(k0, p0);
                sim.calculateEnergy(k1, p1, 0);
                sim.calculateEnergy(k2, p2, 1);
                sim.calculateEnergy(k3, p3, 1, true);
                bool ok1 = std::abs(k0 - k1) < 1e-9 && std::abs(p0 - p1) < 1e-9;
                bool ok2 = std::abs(k0 - k2) < 1e-9 && std::abs(p0 - p2) < 1e-9;
                bool ok3 = std::abs(k0 - k3) < 1e-9 && std::abs(p0 - p3) < 1e-9;
                std::cout << "  calculateEnergy(method=0 default): " << (ok1 ? "OK" : "FAIL") << std::endl;
                std::cout << "  calculateEnergy(method=1 atomic): " << (ok2 ? "OK" : "FAIL") << std::endl;
                std::cout << "  calculateEnergy(method=1 private): " << (ok3 ? "OK" : "FAIL") << std::endl;
            }

            {
                auto sim = make_vsim();
                sim.computeAccelerations();
                sim.processBodies();
                sim.processBodies(0);
                sim.processBodies(1);
                sim.processBodies(0, true);
                sim.simulatePhasesBarrier();
                sim.parallelInitializationSingle();
                double mf = sim.calculateMetricsFirstprivate();
                Particle last = sim.calculateFinalStateLastprivate();
                (void)mf; (void)last;
                std::cout << "  processBodies/PhasesBarrier/Single/Firstprivate/Lastprivate: OK" << std::endl;
            }
        }

    } else {
        std::cout << "--- Modo Benchmark (" << num_particles << " particulas, "
                  << steps << " pasos, " << repetitions << " repeticiones) ---" << std::endl;

        Benchmark bench(repetitions);
        std::ofstream outfile("benchmark_results.dat");
        outfile << "Threads\tMeanTime\tStdDev\tSpeedup\tSpeedupErr\tEfficiency\tEfficiencyErr\tSerialFraction\n";

        auto run_simulation = [&]() {
            NBodySimulator sim(G, epsilon);
            sim.setParticles(initial_particles);

            for (int step = 0; step < steps; ++step) {
                compute_forces(sim);
                sim.integrate(dt);
            }
        };

        std::pair<double, double> serial_stats;

        if (skip_serial && serial_time_override > 0.0) {
            std::cout << "Usando tiempo serial pre-calculado: " << serial_time_override << "s" << std::endl;
            serial_stats = {serial_time_override, 0.0};
        } else {
            std::cout << "Midiendo linea base secuencial (1 hilo)..." << std::endl;
            omp_set_num_threads(1);
            serial_stats = bench.measureExecutionTime(run_simulation);
            std::cout << "Tiempo base: " << serial_stats.first << "s (+/- " << serial_stats.second << "s)\n";
        }

        std::vector<BenchmarkResult> all_results;

        for (int p : thread_counts) {
            std::cout << "Midiendo con " << p << " hilos..." << std::endl;
            omp_set_num_threads(p);
            auto parallel_stats = bench.measureExecutionTime(run_simulation);

            BenchmarkResult res = bench.calculateMetrics(p, serial_stats, parallel_stats);

            outfile << res.threads << "\t" << res.mean_time << "\t" << res.std_dev << "\t"
                    << res.speedup << "\t" << res.speedup_err << "\t"
                    << res.efficiency << "\t" << res.efficiency_err << "\t"
                    << res.serial_fraction << "\n";

            all_results.push_back(res);
        }

        outfile.close();
        std::cout << "\nAnalisis de rendimiento completado. Datos guardados en 'benchmark_results.dat'" << std::endl;

        // Generar scaling_analysis.dat
        std::ofstream scaling_file("scaling_analysis.dat");
        scaling_file << "# Scaling Analysis\n";
        scaling_file << "# Threads\tMeanTime\tSpeedup\tEfficiency\tSerialFraction\tTheoreticalAmdahl\n";
        for (const auto& res : all_results) {
            double p_fraction = 1.0 - res.serial_fraction;
            double theoretical_amdahl = 1.0 / (res.serial_fraction + p_fraction / res.threads);
            scaling_file << res.threads << "\t" << res.mean_time << "\t"
                         << res.speedup << "\t" << res.efficiency << "\t"
                         << res.serial_fraction << "\t" << theoretical_amdahl << "\n";
        }
        scaling_file.close();
        std::cout << "Archivo de escalamiento generado: 'scaling_analysis.dat'" << std::endl;

        if (run_benchmark_all) {
            const int bench_threads = variant_threads;
            omp_set_num_threads(bench_threads);
            Benchmark bench3(extra_repetitions);
            std::cout << "\n--- Benchmarks adicionales (schedule, chunk, sync) con "
                      << bench_threads << " hilos ---" << std::endl;

            // Benchmark A: Comparacion de schedules
            {
                std::ofstream sf("schedule_benchmark.dat");
                sf << "Schedule\tMeanTime\tStdDev\n";
                const char* sn[] = {"static", "dynamic", "guided"};
                for (int s = 0; s <= 2; ++s) {
                    auto task = [&]() {
                        NBodySimulator sim(G, epsilon);
                        sim.setParticles(initial_particles);
                        for (int step = 0; step < steps; ++step) {
                            sim.computeAccelerations(s);
                            sim.integrate(dt);
                        }
                    };
                    auto stats = bench3.measureExecutionTime(task);
                    sf << sn[s] << "\t" << stats.first << "\t" << stats.second << "\n";
                    std::cout << "  Schedule " << sn[s] << ": " << stats.first << " s" << std::endl;
                }
                sf.close();
                std::cout << "  -> schedule_benchmark.dat" << std::endl;
            }

            // Benchmark B: Tamanio de chunk vs tiempo
            {
                std::ofstream cf("chunk_benchmark.dat");
                cf << "Schedule\tChunk\tMeanTime\n";
                int chunks[] = {1, 5, 10, 50, 100, 500};
                for (int s = 0; s <= 2; ++s) {
                    for (int c : chunks) {
                        auto task = [&]() {
                            NBodySimulator sim(G, epsilon);
                            sim.setParticles(initial_particles);
                            for (int step = 0; step < steps; ++step) {
                                sim.computeAccelerations(s, c);
                                sim.integrate(dt);
                            }
                        };
                        auto stats = bench3.measureExecutionTime(task);
                        cf << s << "\t" << c << "\t" << stats.first << "\n";
                    }
                }
                cf.close();
                std::cout << "  Chunk benchmark -> chunk_benchmark.dat" << std::endl;
            }

            // Benchmark C: Comparacion de sincronizacion
            {
                std::ofstream yf("sync_benchmark.dat");
                yf << "SyncType\tMeanTime\tStdDev\n";
                const char* yn[] = {"ATOMIC", "CRITICAL", "NOWAIT", "NORMAL"};
                for (int y = 0; y <= 3; ++y) {
                    auto task = [&]() {
                        NBodySimulator sim(G, epsilon);
                        sim.setParticles(initial_particles);
                        for (int step = 0; step < steps; ++step) {
                            sim.computeAccelerations();
                            sim.integrateEuler(dt, y);
                        }
                    };
                    auto stats = bench3.measureExecutionTime(task);
                    yf << yn[y] << "\t" << stats.first << "\t" << stats.second << "\n";
                    std::cout << "  Sync " << yn[y] << ": " << stats.first << " s" << std::endl;
                }
                yf.close();
                std::cout << "  -> sync_benchmark.dat" << std::endl;
            }

            // Benchmark D: Tareas vs Bucle Paralelo (Sincronización avanzada)
            {
                std::ofstream tf("task_benchmark.dat");
                tf << "TaskType\tMeanTime\tStdDev\n";
                const char* tn[] = {"Task", "ParallelFor"};
                for (int t = 0; t <= 1; ++t) {
                    auto task = [&]() {
                        NBodySimulator sim(G, epsilon);
                        sim.setParticles(initial_particles);
                        for (int step = 0; step < steps; ++step) {
                            sim.computeAccelerations();
                            sim.processBodies(t); // 0 = task, 1 = parallel for
                        }
                    };
                    auto stats = bench3.measureExecutionTime(task);
                    tf << tn[t] << "\t" << stats.first << "\t" << stats.second << "\n";
                    std::cout << "  Sync Avanzada " << tn[t] << ": " << stats.first << " s" << std::endl;
                }
                tf.close();
                std::cout << "  -> task_benchmark.dat" << std::endl;
            }

            // Benchmark E: Memoria (private vs shared implícito en calculateEnergy)
            {
                std::ofstream mf("memory_benchmark.dat");
                mf << "MemoryType\tMeanTime\tStdDev\n";
                const char* mn[] = {"Shared_Atomic", "Private"};
                for (int m = 0; m <= 1; ++m) {
                    auto task = [&]() {
                        NBodySimulator sim(G, epsilon);
                        sim.setParticles(initial_particles);
                        for (int step = 0; step < steps; ++step) {
                            sim.computeAccelerations();
                            double k, p_pot;
                            // m=0 -> atomic (shared), m=1 -> variables privadas
                            sim.calculateEnergy(k, p_pot, 1, m == 1); 
                        }
                    };
                    auto stats = bench3.measureExecutionTime(task);
                    mf << mn[m] << "\t" << stats.first << "\t" << stats.second << "\n";
                    std::cout << "  Memoria " << mn[m] << ": " << stats.first << " s" << std::endl;
                }
                mf.close();
                std::cout << "  -> memory_benchmark.dat" << std::endl;
            }

            // ================================================================
            // Benchmark F: Contención real de sincronización
            // Suma global de energía cinética con critical, atomic, reduction.
            // A diferencia del sync_benchmark (Benchmark C) donde cada hilo
            // escribe a partículas distintas (sin contención), aquí todos los
            // hilos compiten por la misma variable compartida.
            // ================================================================
            {
                std::ofstream ef("energy_sync_benchmark.dat");
                ef << "SyncMethod\tMeanTime\tStdDev\n";
                const char* en[] = {"Critical", "Atomic", "Reduction"};
                for (int e = 0; e <= 2; ++e) {
                    // Usar volatile para evitar que el compilador descarte el resultado
                    volatile double sink = 0.0;
                    auto task = [&]() {
                        NBodySimulator sim(G, epsilon);
                        sim.setParticles(initial_particles);
                        for (int step = 0; step < steps; ++step) {
                            sim.computeAccelerations();
                            sim.integrate(dt);
                            double k = sim.computeKineticSync(e);
                            sink = k;  // forzar materialización del resultado
                        }
                    };
                    auto stats = bench3.measureExecutionTime(task);
                    ef << en[e] << "\t" << stats.first << "\t" << stats.second << "\n";
                    std::cout << "  EnergySync " << en[e] << ": " << stats.first << " s" << std::endl;
                }
                ef.close();
                std::cout << "  -> energy_sync_benchmark.dat" << std::endl;
            }

            // ================================================================
            // Benchmark G: Task vs Parallel-For con trabajo real
            // processBodiesWithWork acumula masa total usando diferentes
            // patrones de sincronización. A diferencia del task_benchmark
            // original (Benchmark D) que mide overhead puro, este mide
            // throughput con trabajo real que el compilador no puede eliminar.
            // ================================================================
            {
                std::ofstream wf("task_work_benchmark.dat");
                wf << "TaskType\tSyncType\tMeanTime\tStdDev\n";
                const char* tn2[] = {"Task", "ParallelFor"};
                const char* sn2[] = {"Atomic", "Critical", "Reduction"};
                for (int t = 0; t <= 1; ++t) {
                    int max_sync = (t == 0) ? 1 : 2;  // task solo tiene atomic/critical
                    for (int s = 0; s <= max_sync; ++s) {
                        volatile double sink = 0.0;
                        auto task = [&]() {
                            NBodySimulator sim(G, epsilon);
                            sim.setParticles(initial_particles);
                            for (int step = 0; step < steps; ++step) {
                                sim.computeAccelerations();
                                sim.integrate(dt);
                                double m = sim.processBodiesWithWork(t, s);
                                sink = m;
                            }
                        };
                        auto stats = bench3.measureExecutionTime(task);
                        wf << tn2[t] << "\t" << sn2[s] << "\t" << stats.first << "\t" << stats.second << "\n";
                        std::cout << "  TaskWork " << tn2[t] << "/" << sn2[s] << ": " << stats.first << " s" << std::endl;
                    }
                }
                wf.close();
                std::cout << "  -> task_work_benchmark.dat" << std::endl;
            }
        }
    }

    return 0;
}
