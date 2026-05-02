#include "NBodySimulator.h"
#include "Integrator.h"
#include <cmath>
#include <fstream>
#include <random>
#include <omp.h>

NBodySimulator::NBodySimulator(double g_const, double eps)
    : G(g_const), epsilon(eps) {}

void NBodySimulator::addParticle(const Particle& p) {
    particles.push_back(p);
}

int NBodySimulator::getNumParticles() const {
    return particles.size();
}

const std::vector<Particle>& NBodySimulator::getParticles() const {
    return particles;
}

void NBodySimulator::computeAccelerations() {
    int n = particles.size();
    
    // 1. Reiniciamos aceleraciones (también se puede paralelizar)
    #pragma omp parallel for schedule(static)
    for (int i = 0; i < n; ++i) {
        particles[i].resetAcceleration();
    }

    // 2. Cálculo de fuerzas O(N^2) paralelizado
    // Usamos schedule(dynamic) por defecto, pero esto es lo que luego
    // cambiarás para hacer los benchmarks que pide el laboratorio.
    #pragma omp parallel for schedule(dynamic)
    for (int i = 0; i < n; ++i) {
        // Cada hilo toma una partícula 'i' y calcula la fuerza que ejercen TODAS las demás 'j'
        for (int j = 0; j < n; ++j) {
            if (i == j) continue;

            double dx = particles[j].getX() - particles[i].getX();
            double dy = particles[j].getY() - particles[i].getY();
            
            double distSq = dx * dx + dy * dy;
            double distSoftened = std::sqrt(distSq + epsilon * epsilon);
            double denominator = distSoftened * distSoftened * distSoftened;
            
            double a_mag = (G * particles[j].getMass()) / denominator;

            // ¡OJO AQUÍ! ¿Hay condición de carrera? 
            // NO, porque el bucle externo paralelo es sobre 'i'.
            // Un hilo modifica particles[1], otro particles[2], etc. 
            // Nunca dos hilos escriben en la MISMA partícula a la vez.
            particles[i].addAcceleration(a_mag * dx, a_mag * dy);
        }
    }
}

// Integrador de Euler (Actualización de posición y velocidad)
void NBodySimulator::integrate(double dt) {
    Integrator::integrateEuler(particles, dt, SyncType::NORMAL);
}

void NBodySimulator::integrateEuler(double dt, int sync_type) {
    SyncType type;
    if (sync_type == 0) type = SyncType::ATOMIC;
    else if (sync_type == 1) type = SyncType::CRITICAL;
    else if (sync_type == 2) type = SyncType::NOWAIT;
    else type = SyncType::NORMAL; 

    Integrator::integrateEuler(particles, dt, type);
}

void NBodySimulator::calculateEnergy(double& kinetic, double& potential) {
    kinetic = 0.0;
    potential = 0.0;
    int n = particles.size();

    // 1. Energía Cinética: Suma de (1/2 * m * v^2)
    // Usamos reduction(+:kinetic) para evitar condiciones de carrera al sumar
    #pragma omp parallel for reduction(+:kinetic)
    for (int i = 0; i < n; ++i) {
        double vx = particles[i].getVx();
        double vy = particles[i].getVy();
        double v2 = vx * vx + vy * vy;
        kinetic += 0.5 * particles[i].getMass() * v2;
    }

    // 2. Energía Potencial Gravitatoria: Suma de (-G * m1 * m2 / r)
    // Usamos schedule(dynamic) y reduction(+:potential)
    #pragma omp parallel for schedule(dynamic) reduction(+:potential)
    for (int i = 0; i < n; ++i) {
        // OJO: j = i + 1. Solo calculamos pares únicos para no duplicar la energía
        for (int j = i + 1; j < n; ++j) { 
            double dx = particles[j].getX() - particles[i].getX();
            double dy = particles[j].getY() - particles[i].getY();
            double distSq = dx * dx + dy * dy;
            double dist = std::sqrt(distSq + epsilon * epsilon); // Evita /0
            
            potential -= (G * particles[i].getMass() * particles[j].getMass()) / dist;
        }
    }
}

bool NBodySimulator::exportState(const std::string& filePath) const {
    std::ofstream out(filePath);
    if (!out.is_open()) {
        return false;
    }

    for (const auto& p : particles) {
        p.writeToStream(out);
        out << '\n';
    }

    return true;
}

void NBodySimulator::initializeRandom(int numParticles,
                                      unsigned int seed,
                                      double posMin, double posMax,
                                      double velMin, double velMax,
                                      double massMin, double massMax) {
    particles.clear();
    particles.reserve(numParticles);

    std::mt19937 gen(seed);
    std::uniform_real_distribution<double> pos_dist(posMin, posMax);
    std::uniform_real_distribution<double> vel_dist(velMin, velMax);
    std::uniform_real_distribution<double> mass_dist(massMin, massMax);

    for (int i = 0; i < numParticles; ++i) {
        particles.emplace_back(
            pos_dist(gen), pos_dist(gen),
            vel_dist(gen), vel_dist(gen),
            mass_dist(gen));
    }
}

