#include "Integrator.h"
#include "NBodyConfig.h"
#include <omp.h>

void Integrator::integrateEuler(std::vector<Particle>& particles, double dt, SyncType sync_type) {
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    Particle* NBODY_RESTRICT p = particles.data();

    switch (sync_type) {
        case SyncType::ATOMIC:
            // Pedagogical slow path: atomics are unnecessary here because each
            // iteration owns a distinct particle. Kept only to measure overhead.
            #pragma omp parallel for schedule(static)
            for (int i = 0; i < n; ++i) {
                const double vx_new = p[i].vx + p[i].ax * dt;
                const double vy_new = p[i].vy + p[i].ay * dt;
                #pragma omp atomic write
                p[i].vx = vx_new;
                #pragma omp atomic write
                p[i].vy = vy_new;
                #pragma omp atomic update
                p[i].x += vx_new * dt;
                #pragma omp atomic update
                p[i].y += vy_new * dt;
            }
            break;

        case SyncType::CRITICAL:
            // Pedagogical worst-case path: serializes updates through one lock.
            #pragma omp parallel for schedule(static)
            for (int i = 0; i < n; ++i) {
                const double vx_new = p[i].vx + p[i].ax * dt;
                const double vy_new = p[i].vy + p[i].ay * dt;
                #pragma omp critical
                {
                    p[i].vx = vx_new;
                    p[i].vy = vy_new;
                    p[i].x += vx_new * dt;
                    p[i].y += vy_new * dt;
                }
            }
            break;

        case SyncType::NOWAIT:
            // The parallel region still has an implicit barrier at its end; this
            // mode exists to demonstrate `nowait`, not to improve this kernel.
            #pragma omp parallel
            {
                #pragma omp for simd nowait schedule(static) aligned(p:64)
                for (int i = 0; i < n; ++i) {
                    const double vx_new = p[i].vx + p[i].ax * dt;
                    const double vy_new = p[i].vy + p[i].ay * dt;
                    p[i].vx = vx_new;
                    p[i].vy = vy_new;
                    p[i].x += vx_new * dt;
                    p[i].y += vy_new * dt;
                }
            }
            break;

        case SyncType::NORMAL:
        default:
            #pragma omp parallel for simd schedule(static) aligned(p:64)
            for (int i = 0; i < n; ++i) {
                const double vx_new = p[i].vx + p[i].ax * dt;
                const double vy_new = p[i].vy + p[i].ay * dt;
                p[i].vx = vx_new;
                p[i].vy = vy_new;
                p[i].x += vx_new * dt;
                p[i].y += vy_new * dt;
            }
            break;
    }
}
