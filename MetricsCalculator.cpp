#include "MetricsCalculator.h"
#include "NBodyConfig.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <omp.h>

std::pair<double, double> MetricsCalculator::calculateTotalMomentum(const std::vector<Particle>& particles) {
    double Px = 0.0;
    double Py = 0.0;
    const int N = static_cast<int>(particles.size());
    if (N == 0) {
        return {0.0, 0.0};
    }

    const Particle* NBODY_RESTRICT p = particles.data();

    #pragma omp parallel for simd schedule(static) aligned(p:64) reduction(+:Px, Py)
    for (int i = 0; i < N; ++i) {
        Px += p[i].mass * p[i].vx;
        Py += p[i].mass * p[i].vy;
    }
    return {Px, Py};
}

std::pair<double, double> MetricsCalculator::calculateCenterOfMass(const std::vector<Particle>& particles) {
    double CMx = 0.0;
    double CMy = 0.0;
    double total_mass = 0.0;
    const int N = static_cast<int>(particles.size());
    if (N == 0) {
        return {0.0, 0.0};
    }

    const Particle* NBODY_RESTRICT p = particles.data();

    #pragma omp parallel for simd schedule(static) aligned(p:64) reduction(+:CMx, CMy, total_mass)
    for (int i = 0; i < N; ++i) {
        CMx += p[i].mass * p[i].x;
        CMy += p[i].mass * p[i].y;
        total_mass += p[i].mass;
    }

    if (total_mass > 0.0) {
        CMx /= total_mass;
        CMy /= total_mass;
    }
    return {CMx, CMy};
}

double MetricsCalculator::calculateRMSRadius(const std::vector<Particle>& particles) {
    const int N = static_cast<int>(particles.size());
    if (N == 0) {
        return 0.0;
    }

    auto cm = calculateCenterOfMass(particles);
    double sum_sq_dist = 0.0;
    const Particle* NBODY_RESTRICT p = particles.data();
    const double cmx = cm.first;
    const double cmy = cm.second;

    #pragma omp parallel for simd schedule(static) aligned(p:64) reduction(+:sum_sq_dist)
    for (int i = 0; i < N; ++i) {
        const double dx = p[i].x - cmx;
        const double dy = p[i].y - cmy;
        sum_sq_dist += dx * dx + dy * dy;
    }

    return std::sqrt(sum_sq_dist / static_cast<double>(N));
}

double MetricsCalculator::calculateMinDistance(const std::vector<Particle>& particles) {
    const int N = static_cast<int>(particles.size());
    if (N < 2) {
        return 0.0;
    }

    double min_dist_sq = std::numeric_limits<double>::max();
    const Particle* NBODY_RESTRICT p = particles.data();

    // Pair loop i<j: half the work of the old i!=j collapse(2) version and no
    // branch in the hot loop. The outer loop is triangular, so dynamic chunks
    // keep load balance without atomics.
    #pragma omp parallel for schedule(dynamic, 8) reduction(min:min_dist_sq)
    for (int i = 0; i < N - 1; ++i) {
        const double xi = p[i].x;
        const double yi = p[i].y;
        double local_min = std::numeric_limits<double>::max();

        #pragma omp simd aligned(p:64) reduction(min:local_min)
        for (int j = i + 1; j < N; ++j) {
            const double dx = xi - p[j].x;
            const double dy = yi - p[j].y;
            const double dist_sq = dx * dx + dy * dy;
            local_min = std::min(local_min, dist_sq);
        }

        min_dist_sq = std::min(min_dist_sq, local_min);
    }

    return std::sqrt(min_dist_sq);
}
