#ifndef CPU_GPU_HARNESS_H
#define CPU_GPU_HARNESS_H

#include <cmath>
#include <string>
#include <vector>
#include <cstddef>
#include "gpu_test_helpers.h"
#include "../NBodySimulator.h"
#include "../MetricsCalculator.h"

// ---------------------------------------------------------------------------
// Configuracion y resultado del harness
// ---------------------------------------------------------------------------

struct HarnessConfig {
    int numBodies = 2;
    double G = 1.0;
    double epsilon = 0.1;
    double dt = 0.01;
    int steps = 1;
    double rtol = kGpuRtol;
    double atol = kGpuAtol;
    unsigned int seed = 42;
    double posMin = -10.0;
    double posMax =  10.0;
    double velMin = -1.0;
    double velMax =  1.0;
    double massMin = 0.5;
    double massMax = 2.0;
};

struct ParticleDelta {
    double ax = 0.0;
    double ay = 0.0;
    double x = 0.0;
    double y = 0.0;
    double vx = 0.0;
    double vy = 0.0;
};

struct HarnessResult {
    bool accelerationsOk = true;
    bool positionsOk = true;
    bool velocitiesOk = true;
    bool allOk = true;
    size_t mismatchCount = 0;
    ParticleDelta maxDelta;
    std::string firstMismatch;
};

// ---------------------------------------------------------------------------
// Helpers internos: inicializacion y computo
// ---------------------------------------------------------------------------

inline void computeStepCpu(NBodySimulator& sim, double dt) {
    sim.computeAccelerations();
    sim.integrate(dt);
}

inline void computeStepGpu(NBodySimulator& sim, double dt) {
    // TODO(gpu): reemplazar cuando R1 entregue stepEulerGpu(dt)
    sim.computeAccelerations();
    sim.integrate(dt);
}

inline void computeAccelerationsCpu(NBodySimulator& sim) {
    sim.computeAccelerations();
}

inline void computeAccelerationsGpu(NBodySimulator& sim) {
    // TODO(gpu): reemplazar cuando R1 entregue computeAccelerationsGpu()
    sim.computeAccelerations();
}

inline void calculateEnergyCpu(NBodySimulator& sim, double& kinetic, double& potential) {
    sim.calculateEnergy(kinetic, potential);
}

inline void calculateEnergyGpu(NBodySimulator& sim, double& kinetic, double& potential) {
    // TODO(gpu): reemplazar cuando R1 entregue calculateEnergyGpu()
    sim.calculateEnergy(kinetic, potential);
}

// ---------------------------------------------------------------------------
// Harness: ejecucion y comparacion
// ---------------------------------------------------------------------------

inline HarnessResult compareAccelerationsOnly(const HarnessConfig& cfg) {
    HarnessResult result;

    NBodySimulator cpuSim(cfg.G, cfg.epsilon);
    NBodySimulator gpuSim(cfg.G, cfg.epsilon);

    cpuSim.initializeRandom(cfg.numBodies, cfg.seed,
                            cfg.posMin, cfg.posMax,
                            cfg.velMin, cfg.velMax,
                            cfg.massMin, cfg.massMax);
    gpuSim.initializeRandom(cfg.numBodies, cfg.seed,
                            cfg.posMin, cfg.posMax,
                            cfg.velMin, cfg.velMax,
                            cfg.massMin, cfg.massMax);

    computeAccelerationsCpu(cpuSim);
    computeAccelerationsGpu(gpuSim);

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();

    if (cpu.size() != gpu.size()) {
        result.accelerationsOk = false;
        result.allOk = false;
        result.firstMismatch = "size cpu=" + std::to_string(cpu.size()) +
                               " gpu=" + std::to_string(gpu.size());
        return result;
    }

    for (size_t i = 0; i < cpu.size(); ++i) {
        double dax = std::fabs(cpu[i].getAx() - gpu[i].getAx());
        double day = std::fabs(cpu[i].getAy() - gpu[i].getAy());

        if (dax > result.maxDelta.ax) result.maxDelta.ax = dax;
        if (day > result.maxDelta.ay) result.maxDelta.ay = day;

        bool axOk = compareFloat(cpu[i].getAx(), gpu[i].getAx(), cfg.rtol, cfg.atol);
        bool ayOk = compareFloat(cpu[i].getAy(), gpu[i].getAy(), cfg.rtol, cfg.atol);

        if (!axOk || !ayOk) {
            ++result.mismatchCount;
            if (result.accelerationsOk) {
                result.accelerationsOk = false;
                result.firstMismatch = "particula " + std::to_string(i);
            }
        }
    }

    result.allOk = result.accelerationsOk;
    return result;
}

inline HarnessResult compareFullStep(const HarnessConfig& cfg) {
    HarnessResult result;

    NBodySimulator cpuSim(cfg.G, cfg.epsilon);
    NBodySimulator gpuSim(cfg.G, cfg.epsilon);

    cpuSim.initializeRandom(cfg.numBodies, cfg.seed,
                            cfg.posMin, cfg.posMax,
                            cfg.velMin, cfg.velMax,
                            cfg.massMin, cfg.massMax);
    gpuSim.initializeRandom(cfg.numBodies, cfg.seed,
                            cfg.posMin, cfg.posMax,
                            cfg.velMin, cfg.velMax,
                            cfg.massMin, cfg.massMax);

    computeStepCpu(cpuSim, cfg.dt);
    computeStepGpu(gpuSim, cfg.dt);

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();

    if (cpu.size() != gpu.size()) {
        result.allOk = false;
        result.firstMismatch = "size cpu=" + std::to_string(cpu.size()) +
                               " gpu=" + std::to_string(gpu.size());
        return result;
    }

    for (size_t i = 0; i < cpu.size(); ++i) {
        double dx  = std::fabs(cpu[i].getX()  - gpu[i].getX());
        double dy  = std::fabs(cpu[i].getY()  - gpu[i].getY());
        double dvx = std::fabs(cpu[i].getVx() - gpu[i].getVx());
        double dvy = std::fabs(cpu[i].getVy() - gpu[i].getVy());
        double dax = std::fabs(cpu[i].getAx() - gpu[i].getAx());
        double day = std::fabs(cpu[i].getAy() - gpu[i].getAy());

        if (dx  > result.maxDelta.x)  result.maxDelta.x  = dx;
        if (dy  > result.maxDelta.y)  result.maxDelta.y  = dy;
        if (dvx > result.maxDelta.vx) result.maxDelta.vx = dvx;
        if (dvy > result.maxDelta.vy) result.maxDelta.vy = dvy;
        if (dax > result.maxDelta.ax) result.maxDelta.ax = dax;
        if (day > result.maxDelta.ay) result.maxDelta.ay = day;

        bool posOk = compareFloat(cpu[i].getX(),  gpu[i].getX(),  cfg.rtol, cfg.atol) &&
                     compareFloat(cpu[i].getY(),  gpu[i].getY(),  cfg.rtol, cfg.atol);
        bool velOk = compareFloat(cpu[i].getVx(), gpu[i].getVx(), cfg.rtol, cfg.atol) &&
                     compareFloat(cpu[i].getVy(), gpu[i].getVy(), cfg.rtol, cfg.atol);
        bool accOk = compareFloat(cpu[i].getAx(), gpu[i].getAx(), cfg.rtol, cfg.atol) &&
                     compareFloat(cpu[i].getAy(), gpu[i].getAy(), cfg.rtol, cfg.atol);

        if (!posOk || !velOk || !accOk) {
            ++result.mismatchCount;
            if (!posOk) result.positionsOk = false;
            if (!velOk) result.velocitiesOk = false;
            if (!accOk) result.accelerationsOk = false;
            if (result.firstMismatch.empty()) {
                result.firstMismatch = "particula " + std::to_string(i);
            }
        }
    }

    result.allOk = result.positionsOk && result.velocitiesOk && result.accelerationsOk;
    return result;
}

inline HarnessResult compareMultiStep(const HarnessConfig& cfg) {
    HarnessResult result;

    NBodySimulator cpuSim(cfg.G, cfg.epsilon);
    NBodySimulator gpuSim(cfg.G, cfg.epsilon);

    cpuSim.initializeRandom(cfg.numBodies, cfg.seed,
                            cfg.posMin, cfg.posMax,
                            cfg.velMin, cfg.velMax,
                            cfg.massMin, cfg.massMax);
    gpuSim.initializeRandom(cfg.numBodies, cfg.seed,
                            cfg.posMin, cfg.posMax,
                            cfg.velMin, cfg.velMax,
                            cfg.massMin, cfg.massMax);

    for (int step = 0; step < cfg.steps; ++step) {
        computeStepCpu(cpuSim, cfg.dt);
        computeStepGpu(gpuSim, cfg.dt);
    }

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();

    if (cpu.size() != gpu.size()) {
        result.allOk = false;
        result.firstMismatch = "size cpu=" + std::to_string(cpu.size()) +
                               " gpu=" + std::to_string(gpu.size());
        return result;
    }

    for (size_t i = 0; i < cpu.size(); ++i) {
        double dx  = std::fabs(cpu[i].getX()  - gpu[i].getX());
        double dy  = std::fabs(cpu[i].getY()  - gpu[i].getY());
        double dvx = std::fabs(cpu[i].getVx() - gpu[i].getVx());
        double dvy = std::fabs(cpu[i].getVy() - gpu[i].getVy());
        double dax = std::fabs(cpu[i].getAx() - gpu[i].getAx());
        double day = std::fabs(cpu[i].getAy() - gpu[i].getAy());

        if (dx  > result.maxDelta.x)  result.maxDelta.x  = dx;
        if (dy  > result.maxDelta.y)  result.maxDelta.y  = dy;
        if (dvx > result.maxDelta.vx) result.maxDelta.vx = dvx;
        if (dvy > result.maxDelta.vy) result.maxDelta.vy = dvy;
        if (dax > result.maxDelta.ax) result.maxDelta.ax = dax;
        if (day > result.maxDelta.ay) result.maxDelta.ay = day;

        bool posOk = compareFloat(cpu[i].getX(),  gpu[i].getX(),  cfg.rtol, cfg.atol) &&
                     compareFloat(cpu[i].getY(),  gpu[i].getY(),  cfg.rtol, cfg.atol);
        bool velOk = compareFloat(cpu[i].getVx(), gpu[i].getVx(), cfg.rtol, cfg.atol) &&
                     compareFloat(cpu[i].getVy(), gpu[i].getVy(), cfg.rtol, cfg.atol);
        bool accOk = compareFloat(cpu[i].getAx(), gpu[i].getAx(), cfg.rtol, cfg.atol) &&
                     compareFloat(cpu[i].getAy(), gpu[i].getAy(), cfg.rtol, cfg.atol);

        if (!posOk || !velOk || !accOk) {
            ++result.mismatchCount;
            if (!posOk) result.positionsOk = false;
            if (!velOk) result.velocitiesOk = false;
            if (!accOk) result.accelerationsOk = false;
            if (result.firstMismatch.empty()) {
                result.firstMismatch = "particula " + std::to_string(i);
            }
        }
    }

    result.allOk = result.positionsOk && result.velocitiesOk && result.accelerationsOk;
    return result;
}

inline HarnessResult compareEnergy(const HarnessConfig& cfg) {
    HarnessResult result;

    NBodySimulator cpuSim(cfg.G, cfg.epsilon);
    NBodySimulator gpuSim(cfg.G, cfg.epsilon);

    cpuSim.initializeRandom(cfg.numBodies, cfg.seed,
                            cfg.posMin, cfg.posMax,
                            cfg.velMin, cfg.velMax,
                            cfg.massMin, cfg.massMax);
    gpuSim.initializeRandom(cfg.numBodies, cfg.seed,
                            cfg.posMin, cfg.posMax,
                            cfg.velMin, cfg.velMax,
                            cfg.massMin, cfg.massMax);

    double cpuK = 0.0, cpuU = 0.0;
    double gpuK = 0.0, gpuU = 0.0;

    computeAccelerationsCpu(cpuSim);
    computeAccelerationsGpu(gpuSim);

    calculateEnergyCpu(cpuSim, cpuK, cpuU);
    calculateEnergyGpu(gpuSim, gpuK, gpuU);

    bool kOk = compareFloat(cpuK, gpuK, cfg.rtol, cfg.atol);
    bool uOk = compareFloat(cpuU, gpuU, cfg.rtol, cfg.atol);

    result.allOk = kOk && uOk;
    if (!kOk || !uOk) {
        result.mismatchCount = 1;
        result.firstMismatch = "energia: cpu_K=" + std::to_string(cpuK) +
                               " gpu_K=" + std::to_string(gpuK) +
                               " cpu_U=" + std::to_string(cpuU) +
                               " gpu_U=" + std::to_string(gpuU);
    }

    return result;
}

inline HarnessResult comparePhysicalInvariants(const HarnessConfig& cfg) {
    HarnessResult result;

    NBodySimulator cpuSim(cfg.G, cfg.epsilon);
    NBodySimulator gpuSim(cfg.G, cfg.epsilon);

    cpuSim.initializeRandom(cfg.numBodies, cfg.seed,
                            cfg.posMin, cfg.posMax,
                            cfg.velMin, cfg.velMax,
                            cfg.massMin, cfg.massMax);
    gpuSim.initializeRandom(cfg.numBodies, cfg.seed,
                            cfg.posMin, cfg.posMax,
                            cfg.velMin, cfg.velMax,
                            cfg.massMin, cfg.massMax);

    computeStepCpu(cpuSim, cfg.dt);
    computeStepGpu(gpuSim, cfg.dt);

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();

    auto cpu_P = MetricsCalculator::calculateTotalMomentum(cpu);
    auto gpu_P = MetricsCalculator::calculateTotalMomentum(gpu);

    auto cpu_CM = MetricsCalculator::calculateCenterOfMass(cpu);
    auto gpu_CM = MetricsCalculator::calculateCenterOfMass(gpu);

    double cpu_rms = MetricsCalculator::calculateRMSRadius(cpu);
    double gpu_rms = MetricsCalculator::calculateRMSRadius(gpu);

    bool pxOk = compareFloat(cpu_P.first,  gpu_P.first,  cfg.rtol, cfg.atol);
    bool pyOk = compareFloat(cpu_P.second, gpu_P.second, cfg.rtol, cfg.atol);
    bool cmxOk = compareFloat(cpu_CM.first,  gpu_CM.first,  cfg.rtol, cfg.atol);
    bool cmyOk = compareFloat(cpu_CM.second, gpu_CM.second, cfg.rtol, cfg.atol);
    bool rmsOk = compareFloat(cpu_rms, gpu_rms, cfg.rtol, cfg.atol);

    result.allOk = pxOk && pyOk && cmxOk && cmyOk && rmsOk;

    if (!result.allOk) {
        result.mismatchCount = 1;
        result.firstMismatch =
            "Px cpu=" + std::to_string(cpu_P.first) + " gpu=" + std::to_string(gpu_P.first) +
            " Py cpu=" + std::to_string(cpu_P.second) + " gpu=" + std::to_string(gpu_P.second);
    }

    return result;
}

#endif
