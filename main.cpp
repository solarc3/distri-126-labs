#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <omp.h>
#include <fstream>
#include <vector>
#include <random>
#include "NBodySimulator.h"
#include "Benchmark.h"
#include "MetricsCalculator.h"

int main(int argc, char* argv[]) {
    double G = 1.0;          
    double epsilon = 0.1;   
    double dt = 0.01;        
    int steps = 100;         
    int num_particles = 2000; 
    int output_every = 10;

    unsigned int seed = 42;
    // Leer argumento para activar el Benchmark
    bool run_benchmark = false;
    if (argc > 1) {
        if (std::string(argv[1]) == "--benchmark") {
            run_benchmark = true;
        } else {
            seed = static_cast<unsigned int>(std::stoul(argv[1]));
        }
    }

    // 1. Generar condiciones iniciales reproducibles y guardarlas
    // Esto es vital para que las ejecuciones del benchmark sean justas
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
        // ==============================================================
        // MODO NORMAL: Calcular y Exportar Métricas Físicas
        // Ejecución: ./tu_programa
        // ==============================================================
        std::cout << "--- Modo Fisica (" << num_particles << " particulas) ---" << std::endl;
        std::cout << "Semilla: " << seed << std::endl;
        
        NBodySimulator sim(G, epsilon);
        for (const auto& p : initial_particles) {
            sim.addParticle(p);
        }

        std::ofstream metrics_file("physics_metrics.dat");
        metrics_file << "Step\tKinetic\tPotential\tTotal\tPx\tPy\tCMx\tCMy\tRMS_Radius\tMinDist\n";

        double start = omp_get_wtime();
        for (int step = 0; step < steps; ++step) {
            sim.computeAccelerations();
            sim.integrate(dt);

            // Exportar estado cada output_every pasos
            if (step % output_every == 0) {
                std::ostringstream name;
                name << "state_" << std::setw(4) << std::setfill('0') << step << ".dat";
                sim.exportState(name.str());
                
                double kin, pot;
                sim.calculateEnergy(kin, pot);
                
                const auto& particles = sim.getParticles(); 
                
                auto P = MetricsCalculator::calculateTotalMomentum(particles);
                auto CM = MetricsCalculator::calculateCenterOfMass(particles);
                double rms = MetricsCalculator::calculateRMSRadius(particles);
                double min_dist = MetricsCalculator::calculateMinDistance(particles);

                metrics_file << step << "\t" << kin << "\t" << pot << "\t" << (kin + pot) << "\t"
                             << P.first << "\t" << P.second << "\t" 
                             << CM.first << "\t" << CM.second << "\t" 
                             << rms << "\t" << min_dist << "\n";
                
                std::cout << "Paso " << step << " procesado y registrado..." << std::endl;
            }
        }
        metrics_file.close();
        double end = omp_get_wtime();
        std::cout << "\nTiempo de ejecucion: " << (end - start) << " segundos" << std::endl;
        std::cout << "Metricas guardadas exitosamente en 'physics_metrics.dat'" << std::endl;

    } else {
        // ==============================================================
        // MODO BENCHMARK: Rendimiento y Escalabilidad
        // Ejecución: ./tu_programa --benchmark
        // ==============================================================
        std::cout << "--- Modo Benchmark (" << num_particles << " particulas) ---" << std::endl;
        
        Benchmark bench(10); // 10 repeticiones estadísticas por configuración
        std::ofstream outfile("benchmark_results.dat");
        outfile << "Threads\tMeanTime\tStdDev\tSpeedup\tSpeedupErr\tEfficiency\tEfficiencyErr\tSerialFraction\n";

        // Creamos una función lambda que reinicia la simulación desde cero en cada llamada
        auto run_simulation = [&]() {
            NBodySimulator sim(G, epsilon);
            for (const auto& p : initial_particles) sim.addParticle(p);
            
            for (int step = 0; step < steps; ++step) {
                sim.computeAccelerations();
                sim.integrate(dt);
            }
        };

        // 1. Obtener el tiempo Base (1 hilo)
        std::cout << "Midiendo linea base secuencial (1 hilo)..." << std::endl;
        omp_set_num_threads(1);
        auto serial_stats = bench.measureExecutionTime(run_simulation);
        std::cout << "Tiempo base: " << serial_stats.first << "s (+/- " << serial_stats.second << "s)\n";

        // 2. Iterar sobre la cantidad de hilos
        std::vector<int> thread_counts = {2, 4, 8, 16};
        for (int p : thread_counts) {
            std::cout << "Midiendo con " << p << " hilos..." << std::endl;
            omp_set_num_threads(p);
            auto parallel_stats = bench.measureExecutionTime(run_simulation);
            
            BenchmarkResult res = bench.calculateMetrics(p, serial_stats, parallel_stats);
            
            // Guardar al archivo .dat
            outfile << res.threads << "\t" << res.mean_time << "\t" << res.std_dev << "\t" 
                    << res.speedup << "\t" << res.speedup_err << "\t" 
                    << res.efficiency << "\t" << res.efficiency_err << "\t" 
                    << res.serial_fraction << "\n";
        }
        
        outfile.close();
        std::cout << "\nAnalisis de rendimiento completado. Datos guardados en 'benchmark_results.dat'" << std::endl;
    }

    return 0;
}