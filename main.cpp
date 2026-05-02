#include <iostream>
#include <iomanip>
#include <random>
#include <omp.h>
#include "NBodySimulator.h"

int main() {
    double G = 1.0;          
    double epsilon = 0.1;   
    double dt = 0.01;        
    int steps = 100;         
    int num_particles = 2000; 

    NBodySimulator sim(G, epsilon);
    std::mt19937 gen(42); 
    std::uniform_real_distribution<double> pos_dist(-10.0, 10.0);
    std::uniform_real_distribution<double> vel_dist(-1.0, 1.0);
    std::uniform_real_distribution<double> mass_dist(0.5, 2.0);

    for (int i = 0; i < num_particles; ++i) {
        sim.addParticle(Particle(pos_dist(gen), pos_dist(gen), vel_dist(gen), vel_dist(gen), mass_dist(gen)));
    }

    std::cout << "Simulacion N-Body (" << num_particles << " particulas)" << std::endl;

    double start = omp_get_wtime();
    for (int step = 0; step < steps; ++step) {
        sim.computeAccelerations();
        sim.integrate(dt);
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