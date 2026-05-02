#ifndef NBODYSIMULATOR_H
#define NBODYSIMULATOR_H

#include <string>
#include <vector>
#include "Particle.h"

class NBodySimulator {
private:
    std::vector<Particle> particles;
    double G;
    double epsilon;

public:
    NBodySimulator(double g_const, double eps);

    void addParticle(const Particle& p);

    void computeAccelerations();
    void computeAccelerations(int schedule_type);
    void computeAccelerations(int schedule_type, int chunk_size);
    void computeAccelerationsCollapse();

    void integrate(double dt);

    void integrateEuler(double dt, int sync_type);
    void integrateEuler(double dt, int sync_type, bool use_barrier);

    int getNumParticles() const;

    const std::vector<Particle>& getParticles() const;

    void calculateEnergy(double& kinetic, double& potential);
    void calculateEnergy(double& kinetic, double& potential, int method);
    void calculateEnergy(double& kinetic, double& potential, int method, bool use_private);

    void processBodies();
    void processBodies(int task_type);
    void processBodies(int task_type, bool use_single);

    void simulatePhasesBarrier();
    void parallelInitializationSingle();
    double calculateMetricsFirstprivate();
    Particle calculateFinalStateLastprivate();

    void initializeRandom(int numParticles,
                          unsigned int seed,
                          double posMin, double posMax,
                          double velMin, double velMax,
                          double massMin, double massMax);
};

#endif
