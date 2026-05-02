#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <omp.h>
#include "NBodySimulator.h"

int main(int argc, char** argv) {
    double G = 1.0;          
    double epsilon = 0.1;   
    double dt = 0.01;        
    int steps = 100;         
    int num_particles = 2000; 
    int output_every = 10;

    NBodySimulator sim(G, epsilon);
    unsigned int seed = 42;
    if (argc > 1) {
        seed = static_cast<unsigned int>(std::stoul(argv[1]));
    }
    sim.initializeRandom(
        num_particles,
        seed,
        -10.0, 10.0,
        -1.0, 1.0,
        0.5, 2.0);

    std::cout << "Simulacion N-Body (" << num_particles << " particulas)" << std::endl;
    std::cout << "Semilla: " << seed << std::endl;

    double start = omp_get_wtime();
    for (int step = 0; step < steps; ++step) {
        sim.computeAccelerations();
        sim.integrate(dt);
        if (step % output_every == 0) {
            std::ostringstream name;
            name << "state_" << std::setw(4) << std::setfill('0') << step << ".dat";
            if (!sim.exportState(name.str())) {
                std::cerr << "No se pudo escribir: " << name.str() << std::endl;
                return 1;
            }
        }
        if (step % 20 == 0) std::cout << "Paso " << step << " procesado..." << std::endl;
    }
    double end = omp_get_wtime();

    double kin, pot;
    sim.calculateEnergy(kin, pot);

    std::cout << "\n--- Resultados ---" << std::endl;
    std::cout << "Tiempo de ejecucion: " << (end - start) << " segundos" << std::endl;
    std::cout << "Energia Cinetica: " << kin << std::endl;
    std::cout << "Energia Potencial: " << pot << std::endl;
    std::cout << "Energia Total: " << (kin + pot) << std::endl;

    return 0;
}