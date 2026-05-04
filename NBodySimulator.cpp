#include "NBodySimulator.h"
#include "Integrator.h"
#include <cmath>
#include <random>
#include <iostream>
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
    computeAccelerations(1);
}

void NBodySimulator::computeAccelerations(int schedule_type) {
    int n = particles.size();

    for (int i = 0; i < n; ++i) {
        particles[i].resetAcceleration();
    }

    switch (schedule_type) {
        case 0: // static
            #pragma omp parallel for schedule(static)
            for (int i = 0; i < n; ++i) {
                for (int j = 0; j < n; ++j) {
                    if (i == j) continue;
                    double dx = particles[j].x - particles[i].x;
                    double dy = particles[j].y - particles[i].y;
                    double distSq = dx * dx + dy * dy;
                    double distSoftened = std::sqrt(distSq + epsilon * epsilon);
                    double denominator = distSoftened * distSoftened * distSoftened;
                    double a_mag = (G * particles[j].mass) / denominator;
                    particles[i].addAcceleration(a_mag * dx, a_mag * dy);
                }
            }
            break;
        case 1: // dynamic
            #pragma omp parallel for schedule(dynamic)
            for (int i = 0; i < n; ++i) {
                for (int j = 0; j < n; ++j) {
                    if (i == j) continue;
                    double dx = particles[j].x - particles[i].x;
                    double dy = particles[j].y - particles[i].y;
                    double distSq = dx * dx + dy * dy;
                    double distSoftened = std::sqrt(distSq + epsilon * epsilon);
                    double denominator = distSoftened * distSoftened * distSoftened;
                    double a_mag = (G * particles[j].mass) / denominator;
                    particles[i].addAcceleration(a_mag * dx, a_mag * dy);
                }
            }
            break;
        case 2: // guided
            #pragma omp parallel for schedule(guided)
            for (int i = 0; i < n; ++i) {
                for (int j = 0; j < n; ++j) {
                    if (i == j) continue;
                    double dx = particles[j].x - particles[i].x;
                    double dy = particles[j].y - particles[i].y;
                    double distSq = dx * dx + dy * dy;
                    double distSoftened = std::sqrt(distSq + epsilon * epsilon);
                    double denominator = distSoftened * distSoftened * distSoftened;
                    double a_mag = (G * particles[j].mass) / denominator;
                    particles[i].addAcceleration(a_mag * dx, a_mag * dy);
                }
            }
            break;
        default:
            computeAccelerations();
            return;
    }
}

void NBodySimulator::computeAccelerations(int schedule_type, int chunk_size) {
    int n = particles.size();

    for (int i = 0; i < n; ++i) {
        particles[i].resetAcceleration();
    }

    switch (schedule_type) {
        case 0: // static with chunk
            #pragma omp parallel for schedule(static, chunk_size)
            for (int i = 0; i < n; ++i) {
                for (int j = 0; j < n; ++j) {
                    if (i == j) continue;
                    double dx = particles[j].x - particles[i].x;
                    double dy = particles[j].y - particles[i].y;
                    double distSq = dx * dx + dy * dy;
                    double distSoftened = std::sqrt(distSq + epsilon * epsilon);
                    double denominator = distSoftened * distSoftened * distSoftened;
                    double a_mag = (G * particles[j].mass) / denominator;
                    particles[i].addAcceleration(a_mag * dx, a_mag * dy);
                }
            }
            break;
        case 1: // dynamic with chunk
            #pragma omp parallel for schedule(dynamic, chunk_size)
            for (int i = 0; i < n; ++i) {
                for (int j = 0; j < n; ++j) {
                    if (i == j) continue;
                    double dx = particles[j].x - particles[i].x;
                    double dy = particles[j].y - particles[i].y;
                    double distSq = dx * dx + dy * dy;
                    double distSoftened = std::sqrt(distSq + epsilon * epsilon);
                    double denominator = distSoftened * distSoftened * distSoftened;
                    double a_mag = (G * particles[j].mass) / denominator;
                    particles[i].addAcceleration(a_mag * dx, a_mag * dy);
                }
            }
            break;
        case 2: // guided with chunk
            #pragma omp parallel for schedule(guided, chunk_size)
            for (int i = 0; i < n; ++i) {
                for (int j = 0; j < n; ++j) {
                    if (i == j) continue;
                    double dx = particles[j].x - particles[i].x;
                    double dy = particles[j].y - particles[i].y;
                    double distSq = dx * dx + dy * dy;
                    double distSoftened = std::sqrt(distSq + epsilon * epsilon);
                    double denominator = distSoftened * distSoftened * distSoftened;
                    double a_mag = (G * particles[j].mass) / denominator;
                    particles[i].addAcceleration(a_mag * dx, a_mag * dy);
                }
            }
            break;
        default:
            computeAccelerations();
            return;
    }
}

void NBodySimulator::computeAccelerationsCollapse() {
    int n = particles.size();

    for (int i = 0; i < n; ++i) {
        particles[i].resetAcceleration();
    }

    #pragma omp parallel for schedule(dynamic) collapse(2)
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            if (i == j) continue;

            double dx = particles[j].x - particles[i].x;
            double dy = particles[j].y - particles[i].y;

            double distSq = dx * dx + dy * dy;
            double distSoftened = std::sqrt(distSq + epsilon * epsilon);
            double denominator = distSoftened * distSoftened * distSoftened;

            double a_mag = (G * particles[j].mass) / denominator;

            #pragma omp atomic
            particles[i].ax += a_mag * dx;
            #pragma omp atomic
            particles[i].ay += a_mag * dy;
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

    int n = particles.size();

    #pragma omp parallel
    {
        #pragma omp for nowait
        for (int i = 0; i < n; ++i) {
            particles[i].vx += particles[i].ax * dt;
            particles[i].vy += particles[i].ay * dt;
        }

        #pragma omp barrier

        #pragma omp for nowait
        for (int i = 0; i < n; ++i) {
            particles[i].x += particles[i].vx * dt;
            particles[i].y += particles[i].vy * dt;
        }
    }
}

void NBodySimulator::calculateEnergy(double& kinetic, double& potential) {
    kinetic = 0.0;
    potential = 0.0;
    int n = particles.size();

    #pragma omp parallel for reduction(+:kinetic)
    for (int i = 0; i < n; ++i) {
        double vx = particles[i].vx;
        double vy = particles[i].vy;
        double v2 = vx * vx + vy * vy;
        kinetic += 0.5 * particles[i].mass * v2;
    }

    #pragma omp parallel for schedule(dynamic) reduction(+:potential)
    for (int i = 0; i < n; ++i) {
        for (int j = i + 1; j < n; ++j) {
            double dx = particles[j].x - particles[i].x;
            double dy = particles[j].y - particles[i].y;
            double distSq = dx * dx + dy * dy;
            double dist = std::sqrt(distSq + epsilon * epsilon);

            potential -= (G * particles[i].mass * particles[j].mass) / dist;
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
    int n = particles.size();

    // Method 1: atomic accumulation
    #pragma omp parallel for schedule(dynamic)
    for (int i = 0; i < n; ++i) {
        double vx = particles[i].vx;
        double vy = particles[i].vy;
        double v2 = vx * vx + vy * vy;
        double local_kin = 0.5 * particles[i].mass * v2;

        #pragma omp atomic
        kinetic += local_kin;

        double local_pot = 0.0;
        for (int j = i + 1; j < n; ++j) {
            double dx = particles[j].x - particles[i].x;
            double dy = particles[j].y - particles[i].y;
            double distSq = dx * dx + dy * dy;
            double dist = std::sqrt(distSq + epsilon * epsilon);
            local_pot -= (G * particles[i].mass * particles[j].mass) / dist;
        }

        #pragma omp atomic
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
    int n = particles.size();

    double priv_kinetic;
    double priv_potential;

    #pragma omp parallel private(priv_kinetic, priv_potential)
    {
        priv_kinetic = 0.0;
        priv_potential = 0.0;

        #pragma omp for schedule(dynamic)
        for (int i = 0; i < n; ++i) {
            double vx = particles[i].vx;
            double vy = particles[i].vy;
            double v2 = vx * vx + vy * vy;
            priv_kinetic += 0.5 * particles[i].mass * v2;

            for (int j = i + 1; j < n; ++j) {
                double dx = particles[j].x - particles[i].x;
                double dy = particles[j].y - particles[i].y;
                double distSq = dx * dx + dy * dy;
                double dist = std::sqrt(distSq + epsilon * epsilon);
                priv_potential -= (G * particles[i].mass * particles[j].mass) / dist;
            }
        }

        #pragma omp atomic
        kinetic += priv_kinetic;

        #pragma omp atomic
        potential += priv_potential;
    }
}

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
                    #pragma omp task
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

void NBodySimulator::simulatePhasesBarrier() {
    int n = particles.size();
    double dt = 0.01;

    #pragma omp parallel
    {
        #pragma omp for nowait
        for (int i = 0; i < n; ++i) {
            particles[i].vx += particles[i].ax * dt;
            particles[i].vy += particles[i].ay * dt;
        }

        #pragma omp barrier

        #pragma omp for nowait
        for (int i = 0; i < n; ++i) {
            particles[i].x += particles[i].vx * dt;
            particles[i].y += particles[i].vy * dt;
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
