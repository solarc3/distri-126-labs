#include "Integrator.h"
#include <omp.h>

void Integrator::integrateEuler(std::vector<Particle>& particles, double dt, SyncType sync_type) {
    int n = particles.size();

    switch (sync_type) {
        case SyncType::ATOMIC:
            #pragma omp parallel for
            for (int i = 0; i < n; ++i) {
                #pragma omp atomic
                particles[i].vx += particles[i].ax * dt;
                #pragma omp atomic
                particles[i].vy += particles[i].ay * dt;
                #pragma omp atomic
                particles[i].x += particles[i].vx * dt;
                #pragma omp atomic
                particles[i].y += particles[i].vy * dt;
            }
            break;

        case SyncType::CRITICAL:
            #pragma omp parallel for
            for (int i = 0; i < n; ++i) {
                #pragma omp critical
                {
                    particles[i].vx += particles[i].ax * dt;
                    particles[i].vy += particles[i].ay * dt;
                    particles[i].x += particles[i].vx * dt;
                    particles[i].y += particles[i].vy * dt;
                }
            }
            break;

        case SyncType::NOWAIT:
            #pragma omp parallel
            {
                #pragma omp for nowait
                for (int i = 0; i < n; ++i) {
                    particles[i].vx += particles[i].ax * dt;
                    particles[i].vy += particles[i].ay * dt;
                    particles[i].x += particles[i].vx * dt;
                    particles[i].y += particles[i].vy * dt;
                }
            }
            break;

        case SyncType::NORMAL:
        default:
            #pragma omp parallel for
            for (int i = 0; i < n; ++i) {
                particles[i].vx += particles[i].ax * dt;
                particles[i].vy += particles[i].ay * dt;
                particles[i].x += particles[i].vx * dt;
                particles[i].y += particles[i].vy * dt;
            }
            break;
    }
}
