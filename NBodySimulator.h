#ifndef NBODYSIMULATOR_H
#define NBODYSIMULATOR_H

#include <memory>
#include <string>
#include <vector>
#include "AlignedAllocator.h"
#include "CudaDeviceSoA.h"
#include "NBodyConfig.h"
#include "Particle.h"

class NBodySimulator {
private:
    using AlignedDoubleVector = std::vector<double, AlignedAllocator<double, nbody_config::CACHE_LINE_BYTES>>;

    std::vector<Particle> particles;
    double G;
    double epsilon;

    // Reusable Structure-of-Arrays buffers for the force kernel.
    // They are 64-byte aligned so the inner loop can safely use aligned SIMD loads.
    AlignedDoubleVector soa_x, soa_y, soa_mass;
    AlignedDoubleVector soa_ax, soa_ay;

    // GPU device buffers (RAII, soporta compilacion sin CUDA via fallback)
    CudaDeviceSoA deviceSoa_;

    void launchGpuKernel(int n, int variant, int block_size);

    void ensureSoABuffers(int n);
    void syncSoAFromParticles(int n);
    void syncAccelerationsToParticles(int n);
    void computeAccelerationsKernel(int n, int schedule_type, int chunk_size, bool use_chunk);
    void computeAccelerationsSoAImpl(int schedule_type, int chunk_size, bool use_chunk);

public:
    NBodySimulator(double g_const, double eps);

    void reserveParticles(int n);
    void setParticles(const std::vector<Particle>& source);
    void addParticle(const Particle& p);

    // Force calculation. The project keeps the schedule/chunk overloads because
    // the benchmark suite uses them, but all of them execute the same SoA kernel.
    void computeAccelerations();
    void computeAccelerations(int schedule_type);
    void computeAccelerations(int schedule_type, int chunk_size);
    void computeAccelerationsSoA();

    // ---- GPU acceleration ----
    // variant: 0 = kernel básico, 1 = shared memory (futuro)
    // block_size: tamaño de bloque CUDA (default=256 si <= 0)
    void computeAccelerationsGpu();
    void computeAccelerationsGpu(int variant);
    void computeAccelerationsGpu(int variant, int block_size);
    void uploadGpuBuffers();
    void computeAccelerationsGpuKernelOnly(int variant, int block_size);
    void downloadGpuAccelerations();

    // Paso completo Euler simplectico usando GPU para aceleraciones.
    // Orden fijo del enunciado:
    //   1. launchGpuKernel(variant, block_size)
    //       1a. copyHostToDevice(x, y, mass)
    //       1b. launchComputeAccelerations<<<grid, block>>>(...)
    //       1c. cudaDeviceSynchronize()
    //       1d. copyDeviceToHost(ax, ay)
    //       1e. syncAccelerationsToParticles()
    //   2. Euler explicito en host (kick-drift secuencial)
    //       2a. v += a * dt (kick)
    //       2b. r += v * dt (drift)
    void stepEulerGpu(double dt);
    void stepEulerGpu(double dt, int variant);
    void stepEulerGpu(double dt, int variant, int block_size);

    void integrate(double dt);

    void integrateEuler(double dt, int sync_type);
    void integrateEuler(double dt, int sync_type, bool use_barrier);

    int getNumParticles() const;

    const std::vector<Particle>& getParticles() const;

    void calculateEnergy(double& kinetic, double& potential);
    void calculateEnergy(double& kinetic, double& potential, int method);
    void calculateEnergy(double& kinetic, double& potential, int method, bool use_private);

    // ---- GPU energy ----
    // method: 0 = reduccion en shared memory (kernel GPU)
    void calculateEnergyGpu(double& kinetic, double& potential, int method = 0);

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
