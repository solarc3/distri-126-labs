#include "MetricsCalculator.h"
#include <cmath>
#include <limits>
#include <omp.h>

std::pair<double, double> MetricsCalculator::calculateTotalMomentum(const std::vector<Particle>& particles) {
    double Px = 0.0;
    double Py = 0.0;
    int N = particles.size();

    #pragma omp parallel for reduction(+:Px, Py)
    for (int i = 0; i < N; ++i) {
        Px += particles[i].mass * particles[i].vx;
        Py += particles[i].mass * particles[i].vy;
    }
    return {Px, Py};
}

std::pair<double, double> MetricsCalculator::calculateCenterOfMass(const std::vector<Particle>& particles) {
    double CMx = 0.0;
    double CMy = 0.0;
    double total_mass = 0.0;
    int N = particles.size();

    #pragma omp parallel for reduction(+:CMx, CMy, total_mass)
    for (int i = 0; i < N; ++i) {
        CMx += particles[i].mass * particles[i].x;
        CMy += particles[i].mass * particles[i].y;
        total_mass += particles[i].mass;
    }
    
    if (total_mass > 0) {
        CMx /= total_mass;
        CMy /= total_mass;
    }
    return {CMx, CMy};
}

double MetricsCalculator::calculateRMSRadius(const std::vector<Particle>& particles) {
    auto cm = calculateCenterOfMass(particles);
    double sum_sq_dist = 0.0;
    int N = particles.size();

    #pragma omp parallel for reduction(+:sum_sq_dist)
    for (int i = 0; i < N; ++i) {
        double dx = particles[i].x - cm.first;
        double dy = particles[i].y - cm.second;
        sum_sq_dist += (dx * dx + dy * dy);
    }
    
    return std::sqrt(sum_sq_dist / N);
}

double MetricsCalculator::calculateMinDistance(const std::vector<Particle>& particles) {
    double min_dist_sq = std::numeric_limits<double>::max();
    int N = particles.size();

    // Utilizamos collapse para paralelizar ambos bucles y reduction(min)
    #pragma omp parallel for schedule(dynamic) collapse(2) reduction(min:min_dist_sq)
    for (int i = 0; i < N; ++i) {
        for (int j = 0; j < N; ++j) {
            if (i != j) {
                double dx = particles[i].x - particles[j].x;
                double dy = particles[i].y - particles[j].y;
                double dist_sq = dx * dx + dy * dy;
                if (dist_sq < min_dist_sq) {
                    min_dist_sq = dist_sq;
                }
            }
        }
    }
    return std::sqrt(min_dist_sq);
}