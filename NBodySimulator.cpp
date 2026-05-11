#include "NBodySimulator.h"
#include "Integrator.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <iostream>
#include <random>
#include <omp.h>

namespace {
inline int clamp_positive_chunk(int chunk_size) noexcept {
    return chunk_size > 0 ? chunk_size : 1;
}
}  // namespace

NBodySimulator::NBodySimulator(double g_const, double eps)
    : G(g_const), epsilon(eps) {}

void NBodySimulator::reserveParticles(int n) {
    if (n > 0) {
        particles.reserve(static_cast<std::size_t>(n));
    }
}

void NBodySimulator::setParticles(const std::vector<Particle>& source) {
    const int n = static_cast<int>(source.size());
    particles.resize(source.size());

    const Particle* NBODY_RESTRICT src = source.data();
    Particle* NBODY_RESTRICT dst = particles.data();

    // Parallel copy intentionally first-touches the destination vector with the
    // same OpenMP placement that will later update it. On a two-NUMA-domain
    // c7a.48xlarge this avoids placing the whole particle array on the thread
    // that happened to build the simulator object.
    #pragma omp parallel for schedule(static) if(n > 2048)
    for (int i = 0; i < n; ++i) {
        dst[i] = src[i];
    }
}

void NBodySimulator::addParticle(const Particle& p) {
    particles.push_back(p);
}

int NBodySimulator::getNumParticles() const {
    return static_cast<int>(particles.size());
}

const std::vector<Particle>& NBodySimulator::getParticles() const {
    return particles;
}

void NBodySimulator::ensureSoABuffers(int n) {
    const std::size_t needed = static_cast<std::size_t>(n);
    if (soa_x.size() != needed) {
        soa_x.resize(needed);
        soa_y.resize(needed);
        soa_mass.resize(needed);
    }
}

void NBodySimulator::syncSoAFromParticles(int n) {
    ensureSoABuffers(n);
    if (n == 0) {
        return;
    }

    const Particle* NBODY_RESTRICT p = particles.data();
    double* NBODY_RESTRICT x = soa_x.data();
    double* NBODY_RESTRICT y = soa_y.data();
    double* NBODY_RESTRICT mass = soa_mass.data();

    // Scatter AoS -> SoA.  The destination arrays are 64-byte aligned and
    // contiguous, so the stores are cache-line friendly; the reads are strided
    // because Particle is AoS/padded.
    #pragma omp parallel for simd schedule(static) aligned(p, x, y, mass:64)
    for (int i = 0; i < n; ++i) {
        x[i] = p[i].x;
        y[i] = p[i].y;
        mass[i] = p[i].mass;
    }
}

void NBodySimulator::computeAccelerations() {
    computeAccelerations(0);
}

void NBodySimulator::computeAccelerations(int schedule_type) {
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    const double eps2 = epsilon * epsilon;
    const double g = G;
    Particle* NBODY_RESTRICT p = particles.data();

    auto compute_particle = [&](int i) {
        double ax_local = 0.0;
        double ay_local = 0.0;
        const double xi = p[i].x;
        const double yi = p[i].y;

        if (eps2 > 0.0) {
            // No branch inside the hot loop: the self term is mathematically
            // zero because dx=dy=0, and softening prevents division by zero.
            #pragma omp simd aligned(p:64) reduction(+:ax_local, ay_local)
            for (int j = 0; j < n; ++j) {
                const double dx = p[j].x - xi;
                const double dy = p[j].y - yi;
                const double distSq = dx * dx + dy * dy + eps2;
                const double invDist = 1.0 / std::sqrt(distSq);
                const double invDist3 = invDist * invDist * invDist;
                const double a_mag = g * p[j].mass * invDist3;

                ax_local += a_mag * dx;
                ay_local += a_mag * dy;
            }
        } else {
            // Exact-zero softening needs to skip j==i.  Splitting the loop keeps
            // both ranges branch-free and SIMD-safe.
            #pragma omp simd aligned(p:64) reduction(+:ax_local, ay_local)
            for (int j = 0; j < i; ++j) {
                const double dx = p[j].x - xi;
                const double dy = p[j].y - yi;
                const double distSq = dx * dx + dy * dy;
                const double invDist = 1.0 / std::sqrt(distSq);
                const double invDist3 = invDist * invDist * invDist;
                const double a_mag = g * p[j].mass * invDist3;

                ax_local += a_mag * dx;
                ay_local += a_mag * dy;
            }
            #pragma omp simd aligned(p:64) reduction(+:ax_local, ay_local)
            for (int j = i + 1; j < n; ++j) {
                const double dx = p[j].x - xi;
                const double dy = p[j].y - yi;
                const double distSq = dx * dx + dy * dy;
                const double invDist = 1.0 / std::sqrt(distSq);
                const double invDist3 = invDist * invDist * invDist;
                const double a_mag = g * p[j].mass * invDist3;

                ax_local += a_mag * dx;
                ay_local += a_mag * dy;
            }
        }

        p[i].ax = ax_local;
        p[i].ay = ay_local;
    };

    switch (schedule_type) {
        case 0: // static: best default; every i performs n interactions.
            #pragma omp parallel for schedule(static)
            for (int i = 0; i < n; ++i) {
                compute_particle(i);
            }
            break;
        case 1: // dynamic: useful only for experiments; higher scheduler cost.
            #pragma omp parallel for schedule(dynamic)
            for (int i = 0; i < n; ++i) {
                compute_particle(i);
            }
            break;
        case 2: // guided: useful for experiments; lower overhead than dynamic.
            #pragma omp parallel for schedule(guided)
            for (int i = 0; i < n; ++i) {
                compute_particle(i);
            }
            break;
        default:
            computeAccelerations(0);
            return;
    }
}

void NBodySimulator::computeAccelerations(int schedule_type, int chunk_size) {
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    const int chunk = clamp_positive_chunk(chunk_size);
    const double eps2 = epsilon * epsilon;
    const double g = G;
    Particle* NBODY_RESTRICT p = particles.data();

    auto compute_particle = [&](int i) {
        double ax_local = 0.0;
        double ay_local = 0.0;
        const double xi = p[i].x;
        const double yi = p[i].y;

        if (eps2 > 0.0) {
            #pragma omp simd aligned(p:64) reduction(+:ax_local, ay_local)
            for (int j = 0; j < n; ++j) {
                const double dx = p[j].x - xi;
                const double dy = p[j].y - yi;
                const double distSq = dx * dx + dy * dy + eps2;
                const double invDist = 1.0 / std::sqrt(distSq);
                const double invDist3 = invDist * invDist * invDist;
                const double a_mag = g * p[j].mass * invDist3;

                ax_local += a_mag * dx;
                ay_local += a_mag * dy;
            }
        } else {
            #pragma omp simd aligned(p:64) reduction(+:ax_local, ay_local)
            for (int j = 0; j < i; ++j) {
                const double dx = p[j].x - xi;
                const double dy = p[j].y - yi;
                const double distSq = dx * dx + dy * dy;
                const double invDist = 1.0 / std::sqrt(distSq);
                const double invDist3 = invDist * invDist * invDist;
                const double a_mag = g * p[j].mass * invDist3;

                ax_local += a_mag * dx;
                ay_local += a_mag * dy;
            }
            #pragma omp simd aligned(p:64) reduction(+:ax_local, ay_local)
            for (int j = i + 1; j < n; ++j) {
                const double dx = p[j].x - xi;
                const double dy = p[j].y - yi;
                const double distSq = dx * dx + dy * dy;
                const double invDist = 1.0 / std::sqrt(distSq);
                const double invDist3 = invDist * invDist * invDist;
                const double a_mag = g * p[j].mass * invDist3;

                ax_local += a_mag * dx;
                ay_local += a_mag * dy;
            }
        }

        p[i].ax = ax_local;
        p[i].ay = ay_local;
    };

    switch (schedule_type) {
        case 0:
            #pragma omp parallel for schedule(static, chunk)
            for (int i = 0; i < n; ++i) {
                compute_particle(i);
            }
            break;
        case 1:
            #pragma omp parallel for schedule(dynamic, chunk)
            for (int i = 0; i < n; ++i) {
                compute_particle(i);
            }
            break;
        case 2:
            #pragma omp parallel for schedule(guided, chunk)
            for (int i = 0; i < n; ++i) {
                compute_particle(i);
            }
            break;
        default:
            computeAccelerations(0);
            return;
    }
}

void NBodySimulator::computeAccelerationsCollapse() {
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    Particle* NBODY_RESTRICT p = particles.data();
    const double eps2 = epsilon * epsilon;
    const double g = G;

    #pragma omp parallel for schedule(static)
    for (int i = 0; i < n; ++i) {
        p[i].resetAcceleration();
    }

    // This overload is intentionally kept as a collapse/atomic demonstration.
    // It is not the fast kernel: atomics serialize many updates to the same
    // particle, and the collapsed i,j space loses the natural private reduction
    // over j used by computeAccelerations() and computeAccelerationsSoA().
    #pragma omp parallel for schedule(dynamic) collapse(2)
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            if (i == j && eps2 == 0.0) continue;

            const double dx = p[j].x - p[i].x;
            const double dy = p[j].y - p[i].y;
            const double distSq = dx * dx + dy * dy + eps2;
            const double invDist = 1.0 / std::sqrt(distSq);
            const double invDist3 = invDist * invDist * invDist;
            const double a_mag = g * p[j].mass * invDist3;

            #pragma omp atomic update
            p[i].ax += a_mag * dx;
            #pragma omp atomic update
            p[i].ay += a_mag * dy;
        }
    }
}

void NBodySimulator::computeAccelerationsNewton3() {
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    syncSoAFromParticles(n);

    const int max_threads = omp_get_max_threads();
    newton_row_stride = nbody_config::round_up_to_cache_line_doubles(static_cast<std::size_t>(n));
    const std::size_t buf_size = static_cast<std::size_t>(max_threads) * newton_row_stride;

    if (newton_ax_buffer.size() != buf_size) {
        newton_ax_buffer.resize(buf_size);
        newton_ay_buffer.resize(buf_size);
    }

    const double eps2 = epsilon * epsilon;
    const double g = G;
    const double* NBODY_RESTRICT x = soa_x.data();
    const double* NBODY_RESTRICT y = soa_y.data();
    const double* NBODY_RESTRICT mass = soa_mass.data();
    double* NBODY_RESTRICT ax_base = newton_ax_buffer.data();
    double* NBODY_RESTRICT ay_base = newton_ay_buffer.data();

    // Layout: [thread][particle], with each row rounded up to 64 bytes.
    // Each thread writes only its own row, so there is no atomic and no false
    // sharing.  Zeroing happens inside the parallel region to first-touch pages
    // on the NUMA domain of the owning thread.
    #pragma omp parallel
    {
        const int tid = omp_get_thread_num();
        double* NBODY_RESTRICT ax = ax_base + static_cast<std::size_t>(tid) * newton_row_stride;
        double* NBODY_RESTRICT ay = ay_base + static_cast<std::size_t>(tid) * newton_row_stride;

        std::fill(ax, ax + n, 0.0);
        std::fill(ay, ay + n, 0.0);

        #pragma omp for schedule(dynamic, nbody_config::NEWTON_CHUNK)
        for (int i = 0; i < n - 1; ++i) {
            const double xi = x[i];
            const double yi = y[i];
            const double mi = mass[i];
            double axi = 0.0;
            double ayi = 0.0;

            // j is contiguous in the SoA arrays and in the per-thread output row.
            // The only scalar recurrence is the reduction for particle i.
            #pragma omp simd aligned(x, y, mass, ax, ay:64) reduction(+:axi, ayi)
            for (int j = i + 1; j < n; ++j) {
                const double dx = x[j] - xi;
                const double dy = y[j] - yi;
                const double distSq = dx * dx + dy * dy + eps2;
                const double invDist = 1.0 / std::sqrt(distSq);
                const double invDist3 = invDist * invDist * invDist;
                const double common = g * invDist3;

                axi += common * mass[j] * dx;
                ayi += common * mass[j] * dy;
                ax[j] += -common * mi * dx;
                ay[j] += -common * mi * dy;
            }

            ax[i] += axi;
            ay[i] += ayi;
        }
    }

    Particle* NBODY_RESTRICT p = particles.data();

    // Reduction: O(n * threads) strided reads.  It is intentionally separated
    // from the O(n^2) force loop to keep force updates race-free and atomic-free.
    #pragma omp parallel for schedule(static)
    for (int i = 0; i < n; ++i) {
        double ax_total = 0.0;
        double ay_total = 0.0;

        #pragma omp simd aligned(ax_base, ay_base:64) reduction(+:ax_total, ay_total)
        for (int t = 0; t < max_threads; ++t) {
            const std::size_t idx = static_cast<std::size_t>(t) * newton_row_stride + static_cast<std::size_t>(i);
            ax_total += ax_base[idx];
            ay_total += ay_base[idx];
        }

        p[i].ax = ax_total;
        p[i].ay = ay_total;
    }
}

void NBodySimulator::computeAccelerationsSoA() {
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    syncSoAFromParticles(n);

    const double eps2 = epsilon * epsilon;
    const double g = G;
    const double* NBODY_RESTRICT x = soa_x.data();
    const double* NBODY_RESTRICT y = soa_y.data();
    const double* NBODY_RESTRICT mass = soa_mass.data();
    Particle* NBODY_RESTRICT p = particles.data();

    if (eps2 == 0.0) {
        // Rare path: exact zero softening. Keep it branch-free by splitting the
        // self interaction out of the SIMD loops.
        #pragma omp parallel for schedule(static)
        for (int i = 0; i < n; ++i) {
            double ax_local = 0.0;
            double ay_local = 0.0;
            const double xi = x[i];
            const double yi = y[i];

            #pragma omp simd aligned(x, y, mass:64) reduction(+:ax_local, ay_local)
            for (int j = 0; j < i; ++j) {
                const double dx = x[j] - xi;
                const double dy = y[j] - yi;
                const double distSq = dx * dx + dy * dy;
                const double invDist = 1.0 / std::sqrt(distSq);
                const double invDist3 = invDist * invDist * invDist;
                const double a_mag = g * mass[j] * invDist3;
                ax_local += a_mag * dx;
                ay_local += a_mag * dy;
            }
            #pragma omp simd aligned(x, y, mass:64) reduction(+:ax_local, ay_local)
            for (int j = i + 1; j < n; ++j) {
                const double dx = x[j] - xi;
                const double dy = y[j] - yi;
                const double distSq = dx * dx + dy * dy;
                const double invDist = 1.0 / std::sqrt(distSq);
                const double invDist3 = invDist * invDist * invDist;
                const double a_mag = g * mass[j] * invDist3;
                ax_local += a_mag * dx;
                ay_local += a_mag * dy;
            }

            p[i].ax = ax_local;
            p[i].ay = ay_local;
        }
        return;
    }

    constexpr int i_tile = nbody_config::SOA_I_TILE;
    constexpr int j_tile = nbody_config::SOA_J_TILE;
    static_assert(i_tile > 0, "SOA_I_TILE must be positive");
    static_assert(j_tile > 0, "SOA_J_TILE must be positive");

    // Cache blocking: a j tile of x/y/mass is reused for several i particles
    // before moving to the next tile. With the defaults, 3 * 4096 * 8 = 96 KiB,
    // fitting comfortably in Zen 4's private L2 while leaving room for code and
    // temporary data.  For each i, j is still visited in increasing order.
    #pragma omp parallel
    {
        std::array<double, i_tile> ax_tile{};
        std::array<double, i_tile> ay_tile{};

        #pragma omp for schedule(static)
        for (int ib = 0; ib < n; ib += i_tile) {
            const int i_end = std::min(ib + i_tile, n);
            const int tile_count = i_end - ib;

            for (int ii = 0; ii < tile_count; ++ii) {
                ax_tile[static_cast<std::size_t>(ii)] = 0.0;
                ay_tile[static_cast<std::size_t>(ii)] = 0.0;
            }

            for (int jb = 0; jb < n; jb += j_tile) {
                const int j_end = std::min(jb + j_tile, n);

                for (int ii = 0; ii < tile_count; ++ii) {
                    const int i = ib + ii;
                    const double xi = x[i];
                    const double yi = y[i];
                    double ax_local = ax_tile[static_cast<std::size_t>(ii)];
                    double ay_local = ay_tile[static_cast<std::size_t>(ii)];

                    #pragma omp simd aligned(x, y, mass:64) reduction(+:ax_local, ay_local)
                    for (int j = jb; j < j_end; ++j) {
                        const double dx = x[j] - xi;
                        const double dy = y[j] - yi;
                        const double distSq = dx * dx + dy * dy + eps2;
                        const double invDist = 1.0 / std::sqrt(distSq);
                        const double invDist3 = invDist * invDist * invDist;
                        const double a_mag = g * mass[j] * invDist3;

                        ax_local += a_mag * dx;
                        ay_local += a_mag * dy;
                    }

                    ax_tile[static_cast<std::size_t>(ii)] = ax_local;
                    ay_tile[static_cast<std::size_t>(ii)] = ay_local;
                }
            }

            for (int ii = 0; ii < tile_count; ++ii) {
                const int i = ib + ii;
                p[i].ax = ax_tile[static_cast<std::size_t>(ii)];
                p[i].ay = ay_tile[static_cast<std::size_t>(ii)];
            }
        }
    }
}

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

void NBodySimulator::integrateEuler(double dt, int sync_type, bool use_barrier) {
    if (!use_barrier) {
        integrateEuler(dt, sync_type);
        return;
    }

    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    Particle* NBODY_RESTRICT p = particles.data();

    #pragma omp parallel
    {
        #pragma omp for simd nowait schedule(static) aligned(p:64)
        for (int i = 0; i < n; ++i) {
            p[i].vx += p[i].ax * dt;
            p[i].vy += p[i].ay * dt;
        }

        #pragma omp barrier

        #pragma omp for simd nowait schedule(static) aligned(p:64)
        for (int i = 0; i < n; ++i) {
            p[i].x += p[i].vx * dt;
            p[i].y += p[i].vy * dt;
        }
    }
}

void NBodySimulator::calculateEnergy(double& kinetic, double& potential) {
    kinetic = 0.0;
    potential = 0.0;
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    const Particle* NBODY_RESTRICT p = particles.data();
    const double eps2 = epsilon * epsilon;
    const double g = G;

    #pragma omp parallel
    {
        #pragma omp for simd schedule(static) aligned(p:64) reduction(+:kinetic)
        for (int i = 0; i < n; ++i) {
            const double vx = p[i].vx;
            const double vy = p[i].vy;
            kinetic += 0.5 * p[i].mass * (vx * vx + vy * vy);
        }

        #pragma omp for schedule(dynamic, 8) reduction(+:potential)
        for (int i = 0; i < n - 1; ++i) {
            const double xi = p[i].x;
            const double yi = p[i].y;
            const double mi = p[i].mass;
            double local_potential = 0.0;

            #pragma omp simd aligned(p:64) reduction(+:local_potential)
            for (int j = i + 1; j < n; ++j) {
                const double dx = p[j].x - xi;
                const double dy = p[j].y - yi;
                const double distSq = dx * dx + dy * dy + eps2;
                const double dist = std::sqrt(distSq);
                local_potential -= (g * mi * p[j].mass) / dist;
            }

            potential += local_potential;
        }
    }
}

void NBodySimulator::calculateEnergy(double& kinetic, double& potential, int method) {
    if (method == 0) {
        calculateEnergy(kinetic, potential);
        return;
    }

    kinetic = 0.0;
    potential = 0.0;
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    const Particle* NBODY_RESTRICT p = particles.data();
    const double eps2 = epsilon * epsilon;
    const double g = G;

    // Method 1: intentionally contended atomic accumulation, kept for the
    // synchronization benchmark. Do not use it in production paths.
    #pragma omp parallel for schedule(dynamic, 8)
    for (int i = 0; i < n; ++i) {
        const double vx = p[i].vx;
        const double vy = p[i].vy;
        const double local_kin = 0.5 * p[i].mass * (vx * vx + vy * vy);

        #pragma omp atomic update
        kinetic += local_kin;

        double local_pot = 0.0;
        #pragma omp simd aligned(p:64) reduction(+:local_pot)
        for (int j = i + 1; j < n; ++j) {
            const double dx = p[j].x - p[i].x;
            const double dy = p[j].y - p[i].y;
            const double distSq = dx * dx + dy * dy + eps2;
            const double dist = std::sqrt(distSq);
            local_pot -= (g * p[i].mass * p[j].mass) / dist;
        }

        #pragma omp atomic update
        potential += local_pot;
    }
}

void NBodySimulator::calculateEnergy(double& kinetic, double& potential, int method, bool use_private) {
    if (!use_private) {
        calculateEnergy(kinetic, potential, method);
        return;
    }

    kinetic = 0.0;
    potential = 0.0;
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    const Particle* NBODY_RESTRICT p = particles.data();
    const double eps2 = epsilon * epsilon;
    const double g = G;

    double priv_kinetic;
    double priv_potential;

    #pragma omp parallel private(priv_kinetic, priv_potential)
    {
        priv_kinetic = 0.0;
        priv_potential = 0.0;

        #pragma omp for schedule(dynamic, 8)
        for (int i = 0; i < n; ++i) {
            const double vx = p[i].vx;
            const double vy = p[i].vy;
            priv_kinetic += 0.5 * p[i].mass * (vx * vx + vy * vy);

            double local_pot = 0.0;
            #pragma omp simd aligned(p:64) reduction(+:local_pot)
            for (int j = i + 1; j < n; ++j) {
                const double dx = p[j].x - p[i].x;
                const double dy = p[j].y - p[i].y;
                const double distSq = dx * dx + dy * dy + eps2;
                const double dist = std::sqrt(distSq);
                local_pot -= (g * p[i].mass * p[j].mass) / dist;
            }
            priv_potential += local_pot;
        }

        #pragma omp atomic update
        kinetic += priv_kinetic;

        #pragma omp atomic update
        potential += priv_potential;
    }
}

// =============================================================================
// Benchmark: Sincronización con contención real
// Compara critical, atomic y reduction al acumular energía cinética global.
// A diferencia del sync_benchmark original (índices únicos, sin contención),
// aquí todos los hilos compiten por la misma variable compartida.
// =============================================================================
double NBodySimulator::computeKineticSync(int sync_method) {
    int n = particles.size();
    double total_kinetic = 0.0;

    switch (sync_method) {
        case 0: // critical — un solo hilo a la vez en la zona protegida
            #pragma omp parallel for
            for (int i = 0; i < n; ++i) {
                double vx = particles[i].vx;
                double vy = particles[i].vy;
                double ki = 0.5 * particles[i].mass * (vx * vx + vy * vy);
                #pragma omp critical
                {
                    total_kinetic += ki;
                }
            }
            break;
        case 1: // atomic — instrucción atómica del hardware (más eficiente que critical)
            #pragma omp parallel for
            for (int i = 0; i < n; ++i) {
                double vx = particles[i].vx;
                double vy = particles[i].vy;
                double ki = 0.5 * particles[i].mass * (vx * vx + vy * vy);
                #pragma omp atomic
                total_kinetic += ki;
            }
            break;
        case 2: // reduction — cada hilo acumula en privado, combinación al final
            #pragma omp parallel for reduction(+:total_kinetic)
            for (int i = 0; i < n; ++i) {
                double vx = particles[i].vx;
                double vy = particles[i].vy;
                total_kinetic += 0.5 * particles[i].mass * (vx * vx + vy * vy);
            }
            break;
        default:
            break;
    }
    return total_kinetic;
}

// =============================================================================
// processBodies — Versiones originales (overhead puro)
//
// NOTA: El cómputo dentro del loop es trivial a propósito.
// Sirve para medir el costo de crear/destruir tareas vs parallel-for,
// no como benchmark de throughput. El compilador puede eliminar el
// cómputo muerto, pero el overhead de scheduling permanece.
// =============================================================================
void NBodySimulator::processBodies() {
    int n = particles.size();
    #pragma omp parallel for
    for (int i = 0; i < n; ++i) {
        double scale = particles[i].mass * particles[i].mass;
        (void)scale;
    }
}

void NBodySimulator::processBodies(int task_type) {
    int n = particles.size();
    if (task_type == 0) {
        // Task-based processing
        #pragma omp parallel
        {
            #pragma omp single
            {
                for (int i = 0; i < n; ++i) {
                    #pragma omp task firstprivate(i)
                    {
                        double scale = particles[i].mass * particles[i].x;
                        (void)scale;
                    }
                }
            }
            // implicit taskwait at end of single
        }
    } else {
        // Parallel for processing
        #pragma omp parallel for
        for (int i = 0; i < n; ++i) {
            double scale = particles[i].mass * particles[i].x;
            (void)scale;
        }
    }
}

void NBodySimulator::processBodies(int task_type, bool use_single) {
    int n = particles.size();
    if (task_type == 0) {
        if (use_single) {
            #pragma omp parallel
            {
                #pragma omp single
                {
                    for (int i = 0; i < n; ++i) {
                        #pragma omp task firstprivate(i)
                        {
                            double scale = particles[i].mass * particles[i].x * particles[i].y;
                            (void)scale;
                        }
                    }
                }
            }
        } else {
            #pragma omp parallel
            {
                #pragma omp for
                for (int i = 0; i < n; ++i) {
                    #pragma omp task firstprivate(i)
                    {
                        double scale = particles[i].mass * particles[i].x * particles[i].y;
                        (void)scale;
                    }
                }
            }
        }
    } else {
        if (use_single) {
            #pragma omp parallel
            {
                #pragma omp single
                {
                    #pragma omp taskgroup
                    {
                        for (int i = 0; i < n; ++i) {
                            #pragma omp task firstprivate(i)
                            {
                                double scale = particles[i].mass * particles[i].x * particles[i].y;
                                (void)scale;
                            }
                        }
                    }
                }
            }
        } else {
            #pragma omp parallel for
            for (int i = 0; i < n; ++i) {
                double scale = particles[i].mass * particles[i].x * particles[i].y;
                (void)scale;
            }
        }
    }
}

// =============================================================================
// processBodiesWithWork — Versión con trabajo real
//
// Acumula la masa total del sistema usando diferentes patrones de tareas
// y sincronización. A diferencia de processBodies(), el compilador no puede
// eliminar el cómputo porque el resultado se retorna y se usa fuera.
// =============================================================================
double NBodySimulator::processBodiesWithWork(int task_type, int sync_type) {
    int n = particles.size();
    double total_mass = 0.0;

    if (task_type == 0) {
        // Task-based: cada partícula en su propia tarea
        #pragma omp parallel
        {
            #pragma omp single
            {
                for (int i = 0; i < n; ++i) {
                    #pragma omp task firstprivate(i) shared(total_mass)
                    {
                        double m = particles[i].mass;
                        if (sync_type == 0) {
                            #pragma omp atomic
                            total_mass += m;
                        } else if (sync_type == 1) {
                            #pragma omp critical
                            total_mass += m;
                        }
                        // sync_type == 2 (reduction) no aplica con tasks;
                        // se usa atomic como fallback razonable
                        else {
                            #pragma omp atomic
                            total_mass += m;
                        }
                    }
                }
            }
        }
    } else {
        // Parallel-for con distintos tipos de sincronización
        switch (sync_type) {
            case 0: // atomic
                #pragma omp parallel for
                for (int i = 0; i < n; ++i) {
                    #pragma omp atomic
                    total_mass += particles[i].mass;
                }
                break;
            case 1: // critical
                #pragma omp parallel for
                for (int i = 0; i < n; ++i) {
                    #pragma omp critical
                    total_mass += particles[i].mass;
                }
                break;
            case 2: // reduction (óptimo)
                #pragma omp parallel for reduction(+:total_mass)
                for (int i = 0; i < n; ++i) {
                    total_mass += particles[i].mass;
                }
                break;
            default:
                break;
        }
    }
    return total_mass;
}

void NBodySimulator::simulatePhasesBarrier() {
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    const double dt = 0.01;
    Particle* NBODY_RESTRICT p = particles.data();

    #pragma omp parallel
    {
        #pragma omp for simd nowait schedule(static) aligned(p:64)
        for (int i = 0; i < n; ++i) {
            p[i].vx += p[i].ax * dt;
            p[i].vy += p[i].ay * dt;
        }

        #pragma omp barrier

        #pragma omp for simd nowait schedule(static) aligned(p:64)
        for (int i = 0; i < n; ++i) {
            p[i].x += p[i].vx * dt;
            p[i].y += p[i].vy * dt;
        }
    }
}

void NBodySimulator::parallelInitializationSingle() {
    double total_mass_calc = 0.0;
    #pragma omp parallel
    {
        #pragma omp single
        {
            std::cout << "Inicializando sistema con " << particles.size()
                      << " particulas desde hilo " << omp_get_thread_num() << std::endl;
        }

        #pragma omp for reduction(+:total_mass_calc)
        for (size_t i = 0; i < particles.size(); ++i) {
            total_mass_calc += particles[i].mass;
        }
    }
    std::cout << "Masa total calculada en paralelo: " << total_mass_calc << std::endl;
}

double NBodySimulator::calculateMetricsFirstprivate() {
    double total_mass = 0.0;
    for (size_t i = 0; i < particles.size(); ++i) {
        total_mass += particles[i].mass;
    }

    double thread_sum = 0.0;
    #pragma omp parallel firstprivate(total_mass)
    {
        double local_contrib = 0.0;
        #pragma omp for
        for (size_t i = 0; i < particles.size(); ++i) {
            local_contrib += particles[i].x * particles[i].mass / total_mass;
        }
        #pragma omp atomic
        thread_sum += local_contrib;
    }
    return thread_sum;
}

Particle NBodySimulator::calculateFinalStateLastprivate() {
    size_t last_idx = 0;
    #pragma omp parallel for lastprivate(last_idx)
    for (size_t i = 0; i < particles.size(); ++i) {
        last_idx = i;
    }
    return particles[last_idx];
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
