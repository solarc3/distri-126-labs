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
    void computeAccelerationsNewton3();
    void computeAccelerationsSoA();

    void integrate(double dt);

    void integrateEuler(double dt, int sync_type);
    void integrateEuler(double dt, int sync_type, bool use_barrier);

    int getNumParticles() const;

    const std::vector<Particle>& getParticles() const;

    void calculateEnergy(double& kinetic, double& potential);
    void calculateEnergy(double& kinetic, double& potential, int method);
    void calculateEnergy(double& kinetic, double& potential, int method, bool use_private);

    // --- Benchmarks de sincronización con contención real ---
    // sync_method: 0=critical, 1=atomic, 2=reduction
    // Retorna la energía cinética total (para forzar al compilador a mantener el código)
    double computeKineticSync(int sync_method);

    // --- Benchmarks de tasking y processBodies ---
    // Versión original: mide overhead puro de task/parallel-for (cómputo mínimo)
    // Útil para comparar el costo de creación de tareas vs parallel-for.
    void processBodies();
    void processBodies(int task_type);
    void processBodies(int task_type, bool use_single);

    // Versión con trabajo real: acumula masa total con diferentes patrones de sync.
    // task_type: 0=task, 1=parallel-for
    // sync_type: 0=atomic, 1=critical, 2=reduction
    double processBodiesWithWork(int task_type, int sync_type);

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
