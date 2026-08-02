#include "NBodySimulator.h"
#include "Integrator.h"
#include "kernels/accelerations.cuh"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <random>
#include <omp.h>

namespace {
inline int clamp_positive_chunk(int chunk_size) noexcept {
    return chunk_size > 0 ? chunk_size : 1;
}

inline omp_sched_t to_omp_schedule(int schedule_type) noexcept {
    switch (schedule_type) {
        case 1: return omp_sched_dynamic;
        case 2: return omp_sched_guided;
        case 0:
        default: return omp_sched_static;
    }
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
    // same OpenMP placement that will later update it. On c7a.48xlarge this
    // helps avoid placing the whole particle array on the NUMA node of the
    // thread that happened to build the simulator object.
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
        soa_ax.resize(needed);
        soa_ay.resize(needed);
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

    // AoS -> SoA. The destination arrays are contiguous and 64-byte aligned;
    // this is the layout consumed by the force kernel.
    #pragma omp parallel for simd schedule(static) aligned(p, x, y, mass:64)
    for (int i = 0; i < n; ++i) {
        x[i] = p[i].x;
        y[i] = p[i].y;
        mass[i] = p[i].mass;
    }
}

void NBodySimulator::syncAccelerationsToParticles(int n) {
    if (n == 0) {
        return;
    }

    const double* NBODY_RESTRICT ax = soa_ax.data();
    const double* NBODY_RESTRICT ay = soa_ay.data();
    Particle* NBODY_RESTRICT p = particles.data();

    #pragma omp parallel for simd schedule(static) aligned(ax, ay, p:64)
    for (int i = 0; i < n; ++i) {
        p[i].ax = ax[i];
        p[i].ay = ay[i];
    }
}

void NBodySimulator::computeAccelerations() {
    computeAccelerationsSoAImpl(0, 0, false);
}

void NBodySimulator::computeAccelerations(int schedule_type) {
    computeAccelerationsSoAImpl(schedule_type, 0, false);
}

void NBodySimulator::computeAccelerations(int schedule_type, int chunk_size) {
    computeAccelerationsSoAImpl(schedule_type, clamp_positive_chunk(chunk_size), true);
}

void NBodySimulator::computeAccelerationsSoA() {
    computeAccelerationsSoAImpl(0, 0, false);
}

void NBodySimulator::computeAccelerationsKernel(int n, int schedule_type, int chunk_size, bool use_chunk) {
    if (n == 0) {
        return;
    }

    const double eps2 = epsilon * epsilon;
    const double g = G;
    const double* NBODY_RESTRICT x = soa_x.data();
    const double* NBODY_RESTRICT y = soa_y.data();
    const double* NBODY_RESTRICT mass = soa_mass.data();
    double* NBODY_RESTRICT ax = soa_ax.data();
    double* NBODY_RESTRICT ay = soa_ay.data();
    const bool default_static = (schedule_type == 0 && !use_chunk);

    omp_sched_t previous_kind = omp_sched_static;
    int previous_chunk = 0;
    if (!default_static) {
        omp_get_schedule(&previous_kind, &previous_chunk);
        omp_set_schedule(to_omp_schedule(schedule_type), use_chunk ? chunk_size : 0);
    }

    if (eps2 == 0.0) {
        // Rare path: exact zero softening. The self interaction must be skipped;
        // splitting j keeps the vectorized loops branch-free and finite.
        auto compute_i = [&](int i) {
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

            ax[i] = ax_local;
            ay[i] = ay_local;
        };

        if (default_static) {
            #pragma omp parallel for schedule(static)
            for (int i = 0; i < n; ++i) {
                compute_i(i);
            }
        } else {
            #pragma omp parallel for schedule(runtime)
            for (int i = 0; i < n; ++i) {
                compute_i(i);
            }
            omp_set_schedule(previous_kind, previous_chunk);
        }
        return;
    }

    constexpr int i_tile = nbody_config::SOA_I_TILE;
    constexpr int j_tile = nbody_config::SOA_J_TILE;
    static_assert(i_tile > 0, "SOA_I_TILE must be positive");
    static_assert(j_tile > 0, "SOA_J_TILE must be positive");

    // Cache blocking: a j tile of x/y/mass is reused for several i particles
    // before moving to the next tile. Defaults: 3 * 4096 * 8 = 96 KiB, which is
    // small enough for private cache while still amortizing the tile loads.
    #pragma omp parallel
    {
        std::array<double, i_tile> ax_tile{};
        std::array<double, i_tile> ay_tile{};

        auto compute_ib = [&](int ib) {
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
                ax[i] = ax_tile[static_cast<std::size_t>(ii)];
                ay[i] = ay_tile[static_cast<std::size_t>(ii)];
            }
        };

        if (default_static) {
            #pragma omp for schedule(static)
            for (int ib = 0; ib < n; ib += i_tile) {
                compute_ib(ib);
            }
        } else {
            #pragma omp for schedule(runtime)
            for (int ib = 0; ib < n; ib += i_tile) {
                compute_ib(ib);
            }
        }
    }

    if (!default_static) {
        omp_set_schedule(previous_kind, previous_chunk);
    }
}

void NBodySimulator::computeAccelerationsSoAImpl(int schedule_type, int chunk_size, bool use_chunk) {
    const int n = static_cast<int>(particles.size());
    if (n == 0) {
        return;
    }

    syncSoAFromParticles(n);
    computeAccelerationsKernel(n, schedule_type, chunk_size, use_chunk);
    syncAccelerationsToParticles(n);
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

// ---------------------------------------------------------------------------
// GPU: aceleraciones via CUDA
// ---------------------------------------------------------------------------

void NBodySimulator::launchGpuKernel(int n, int variant, int block_size) {
    if (n == 0) return;

#if defined(NBODY_ENABLE_CUDA_KERNELS)
    syncSoAFromParticles(n);
    double eps2 = epsilon * epsilon;

    deviceSoa_.allocate(n);
    deviceSoa_.copyHostToDevice(soa_x.data(), soa_y.data(), soa_mass.data(), n);

    launchComputeAccelerations(
        deviceSoa_.d_x.data(), deviceSoa_.d_y.data(), deviceSoa_.d_mass.data(),
        deviceSoa_.d_ax.data(), deviceSoa_.d_ay.data(),
        n, G, eps2, variant, block_size);

    deviceSoa_.synchronize();

    deviceSoa_.copyDeviceToHost(soa_ax.data(), soa_ay.data(), n);
    syncAccelerationsToParticles(n);
#else
    (void)variant;
    (void)block_size;
    computeAccelerationsSoAImpl(0, 0, false);
#endif
}

void NBodySimulator::computeAccelerationsGpu() {
    launchGpuKernel(getNumParticles(), 0, 0);
}

void NBodySimulator::computeAccelerationsGpu(int variant) {
    launchGpuKernel(getNumParticles(), variant, 0);
}

void NBodySimulator::computeAccelerationsGpu(int variant, int block_size) {
    launchGpuKernel(getNumParticles(), variant, block_size);
}

void NBodySimulator::stepEulerGpu(double dt) {
    stepEulerGpu(dt, 0, 0);
}

void NBodySimulator::stepEulerGpu(double dt, int variant) {
    stepEulerGpu(dt, variant, 0);
}

void NBodySimulator::stepEulerGpu(double dt, int variant, int block_size) {
    const int n = getNumParticles();
    if (n == 0) return;

    // ---------------------------------------------------------------
    // 1. Kernel de aceleraciones en GPU
    //    1a. syncSoAFromParticles: AoS -> SoA (x,y,mass) [host]
    //    1b. copyHostToDevice: SoA -> device buffers
    //    1c. launchComputeAccelerations<<<grid,block>>>(...) [GPU]
    //    1d. cudaDeviceSynchronize()
    //    1e. copyDeviceToHost: device buffers -> SoA (ax,ay) [host]
    //    1f. syncAccelerationsToParticles: SoA -> particles [host]
    // ---------------------------------------------------------------
    launchGpuKernel(n, variant, block_size);

    // ---------------------------------------------------------------
    // 2. Euler explicito en host (kick-drift secuencial)
    //    Orden fijo: primero kick (v += a*dt), luego drift (r += v*dt)
    //    con las velocidades recien actualizadas (Euler simplectico)
    // ---------------------------------------------------------------
    Particle* NBODY_RESTRICT p = particles.data();
    for (int i = 0; i < n; ++i) {
        const double vx_new = p[i].vx + p[i].ax * dt;
        const double vy_new = p[i].vy + p[i].ay * dt;
        p[i].vx = vx_new;
        p[i].vy = vy_new;
        p[i].x += vx_new * dt;
        p[i].y += vy_new * dt;
    }

    // Las posiciones en host quedan actualizadas. Si el siguiente
    // paso requiere aceleraciones, launchGpuKernel() volvera a
    // copiar host->device desde los SoA actualizados.
}
