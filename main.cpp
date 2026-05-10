#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <omp.h>
#include <fstream>
#include <vector>
#include <random>
#include <cmath>
#include "NBodySimulator.h"
#include "Benchmark.h"
#include "MetricsCalculator.h"
#include "Visualizer.h"

int main(int argc, char* argv[]) {
    double G = 1.0;
    double epsilon = 0.1;
    double dt = 0.01;
    int steps = 100;
    int num_particles = 2000;
    int output_every = 10;

    unsigned int seed = 42;
    bool run_benchmark = false;
    bool run_benchmark_all = false;
    if (argc > 1) {
        std::string arg1(argv[1]);
        if (arg1 == "--benchmark-all") {
            run_benchmark = true;
            run_benchmark_all = true;
        } else if (arg1 == "--benchmark") {
            run_benchmark = true;
        } else {
            seed = static_cast<unsigned int>(std::stoul(argv[1]));
        }
    }

    std::vector<Particle> initial_particles;
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
        for (const auto& p : initial_particles) {
            sim.addParticle(p);
        }
        double t_serial_end = omp_get_wtime();

        std::ofstream metrics_file("energy_timeseries.dat");
        metrics_file << "Step\tKinetic\tPotential\tTotal\tPx\tPy\tCMx\tCMy\tRMS_Radius\tMinDist\tPMag\n";

        double start = omp_get_wtime();
        for (int step = 0; step < steps; ++step) {
            sim.computeAccelerations();
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
                for (const auto& p : vp) s.addParticle(p);
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

            {
                auto sim = make_vsim();
                sim.computeAccelerationsCollapse();
                bool ok = true;
                for (const auto& p : sim.getParticles())
                    if (!std::isfinite(p.getAx()) || !std::isfinite(p.getAy())) { ok = false; break; }
                std::cout << "  computeAccelerationsCollapse(): " << (ok ? "OK" : "FAIL") << std::endl;
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
        std::cout << "--- Modo Benchmark (" << num_particles << " particulas) ---" << std::endl;

        Benchmark bench(10);
        std::ofstream outfile("benchmark_results.dat");
        outfile << "Threads\tMeanTime\tStdDev\tSpeedup\tSpeedupErr\tEfficiency\tEfficiencyErr\tSerialFraction\n";

        auto run_simulation = [&]() {
            NBodySimulator sim(G, epsilon);
            for (const auto& p : initial_particles) sim.addParticle(p);

            for (int step = 0; step < steps; ++step) {
                sim.computeAccelerations();
                sim.integrate(dt);
            }
        };

        std::cout << "Midiendo linea base secuencial (1 hilo)..." << std::endl;
        omp_set_num_threads(1);
        auto serial_stats = bench.measureExecutionTime(run_simulation);
        std::cout << "Tiempo base: " << serial_stats.first << "s (+/- " << serial_stats.second << "s)\n";

        std::vector<int> thread_counts = {2, 4, 8, 16};
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
            const int bench_threads = 4;
            omp_set_num_threads(bench_threads);
            Benchmark bench3(3);
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
                        for (const auto& p : initial_particles) sim.addParticle(p);
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
                            for (const auto& p : initial_particles) sim.addParticle(p);
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
                        for (const auto& p : initial_particles) sim.addParticle(p);
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
                        for (const auto& p : initial_particles) sim.addParticle(p);
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
                        for (const auto& p : initial_particles) sim.addParticle(p);
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
        }
    }

    return 0;
}
