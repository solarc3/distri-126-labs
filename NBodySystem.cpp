#include "NBodySystem.h"
#include <cmath>
#include <omp.h>
#include <random>
#include <fstream>
#include <stdexcept>

NBodySystem::NBodySystem(double G_, double epsilon_) :
    G(G_), epsilon(epsilon_) {} 

void NBodySystem::addParticle(const Particle& p) {
    particles.push_back(p);

}

void NBodySystem::zeroAccelerations() {
    for (auto& p : particles) {
        p.resetAcceleration();
    }
}

void NBodySystem::computeAccelerations() {
    int n = particles.size();

    zeroAccelerations(); 

    for (int i = 0; i < n; ++i) {
        double xi = particles[i].getX();
        double yi = particles[i].getY();
        double ai_x = 0.0;
        double ai_y = 0.0;

        for (int j = 0; j < n; ++j) {
            if (i == j) continue;

            double dx = particles[j].getX() - xi;
            double dy = particles[j].getY() - yi;

            double r2 = dx * dx + dy * dy + epsilon * epsilon;
            double inv_r3 = 1.0 / (r2 * std::sqrt(r2));

            double factor = G * particles[j].getMass() * inv_r3;

            ai_x += factor * dx;
            ai_y += factor * dy;
        }

        particles[i].addAcceleration(ai_x, ai_y);
    }
}

std::vector<Particle>& NBodySystem::getParticles() {
    return particles;
}

int NBodySystem::size() const {
    return particles.size();
}

double NBodySystem::getG() const {
    return G;
}

double NBodySystem::getEpsilon() const {
    return epsilon;
}
