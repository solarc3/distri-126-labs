#include <gtest/gtest.h>
#include <cmath>
#include <vector>
#include <string>
#include "gpu_test_helpers.h"
#include "../NBodySimulator.h"
#include "../MetricsCalculator.h"

// ---------------------------------------------------------------------------
// Helpers locales reutilizables
// ---------------------------------------------------------------------------

static std::vector<Particle> makeTestParticles(int n) {
    std::vector<Particle> particles;
    for (int i = 0; i < n; ++i) {
        particles.emplace_back(
            i * 0.2, i * 0.3 - 1.0,
            0.1 + i * 0.01, -0.05 * i,
            1.0 + (i % 3) * 0.5
        );
    }
    return particles;
}

// ---------------------------------------------------------------------------
// Tests del harness de comparacion (validan compareFloat y helpers)
// ---------------------------------------------------------------------------

TEST(GpuTestHarness, CompareFloatIdenticalValues) {
    EXPECT_TRUE(compareFloat(3.1415926535, 3.1415926535));
    EXPECT_TRUE(compareFloat(0.0, 0.0));
    EXPECT_TRUE(compareFloat(-42.0, -42.0));
}

TEST(GpuTestHarness, CompareFloatWithinAtol) {
    EXPECT_TRUE(compareFloat(0.0, 1e-9));                    // < atol
    EXPECT_TRUE(compareFloat(0.0, kGpuAtol));                // == atol (border)
    EXPECT_TRUE(compareFloat(0.0, -5e-9));                   // negativo < atol
}

TEST(GpuTestHarness, CompareFloatWithinRtol) {
    EXPECT_TRUE(compareFloat(1.0, 1.0 + 5e-5));              // diff < rtol*1.0
    EXPECT_TRUE(compareFloat(1000.0, 1000.0 * (1.0 + kGpuRtol)));
    EXPECT_TRUE(compareFloat(-50.0, -50.0 + 1e-4 * 50.0));
}

TEST(GpuTestHarness, CompareFloatOutsideTolerance) {
    EXPECT_FALSE(compareFloat(1.0, 1.0 + 2e-4));            // diff > rtol para valor ~1
    EXPECT_FALSE(compareFloat(0.0, 2e-8));                  // diff > atol
    EXPECT_FALSE(compareFloat(100.0, 100.0 + 0.1));         // diff grande
}

TEST(GpuTestHarness, CompareFloatMixedSigns) {
    EXPECT_FALSE(compareFloat(1.0, -1.0));                  // diferencia grande
    EXPECT_TRUE(compareFloat(1e-10, -1e-10));               // dentro de atol
}

TEST(GpuTestHarness, CompareParticleStatesMatch) {
    auto cpu = makeTestParticles(10);
    auto gpu = makeTestParticles(10);
    EXPECT_TRUE(compareParticleStates(cpu, gpu));
}

TEST(GpuTestHarness, CompareParticleStatesMismatchDetected) {
    auto cpu = makeTestParticles(10);
    auto gpu = makeTestParticles(10);
    gpu[5] = Particle(999.0, 999.0, 0.0, 0.0, 1.0);
    EXPECT_FALSE(compareParticleStates(cpu, gpu));
    std::string detail = mismatchDetail(cpu, gpu);
    EXPECT_FALSE(detail.empty());
    EXPECT_NE(detail.find("cpu="), std::string::npos);
}

TEST(GpuTestHarness, CompareFloatArrayMatch) {
    std::vector<double> a = {1.0, 2.0, 3.0};
    std::vector<double> b = {1.0, 2.0, 3.0};
    EXPECT_TRUE(compareFloatArray(a, b));
}

TEST(GpuTestHarness, CompareFloatArraySizeMismatch) {
    std::vector<double> a = {1.0, 2.0};
    std::vector<double> b = {1.0};
    EXPECT_FALSE(compareFloatArray(a, b));
}

// ---------------------------------------------------------------------------
// Esqueleto: tests de equivalencia CPU serial vs GPU
// ---------------------------------------------------------------------------
// NOTA: Estos tests contienen placeholders para las llamadas GPU que seran
// provistas por R1/R2. Actualmente comparan CPU vs CPU para validar la
// infraestructura de comparacion. Sustituir los marcadores
// /* TODO(gpu): ... */ cuando las funciones GPU esten disponibles.

TEST(GpuEquivalence, AccelerationsN2) {
    const int N = 2;
    // ------------------------------------------------------------------
    // Preparacion: misma configuracion CPU y GPU
    // ------------------------------------------------------------------
    NBodySimulator cpuSim(1.0, 0.1);
    NBodySimulator gpuSim(1.0, 0.1);

    Particle p1(0.0, 0.0, 0.0, 0.0, 1.0);
    Particle p2(1.0, 0.0, 0.0, 0.0, 1.0);
    cpuSim.addParticle(p1); cpuSim.addParticle(p2);
    gpuSim.addParticle(p1); gpuSim.addParticle(p2);

    // ------------------------------------------------------------------
    // Computo de referencia (CPU serial)
    // ------------------------------------------------------------------
    cpuSim.computeAccelerations();

    // ------------------------------------------------------------------
    // Computo GPU (placeholder: actualmente usa CPU)
    // TODO(gpu): reemplazar por computeAccelerationsGpu() cuando R1 lo entregue
    // ------------------------------------------------------------------
    gpuSim.computeAccelerations();

    // ------------------------------------------------------------------
    // Comparacion con tolerancias de laboratorio
    // ------------------------------------------------------------------
    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();

    EXPECT_EQ(cpu.size(), gpu.size());
    for (int i = 0; i < N; ++i) {
        SCOPED_TRACE("particula " + std::to_string(i));
        EXPECT_TRUE(compareAccelerations(cpu[i], gpu[i]))
            << "ax=" << cpu[i].getAx() << " vs " << gpu[i].getAx()
            << " ay=" << cpu[i].getAy() << " vs " << gpu[i].getAy();
    }
}

TEST(GpuEquivalence, AccelerationsN3) {
    const int N = 3;
    NBodySimulator cpuSim(1.0, 0.1);
    NBodySimulator gpuSim(1.0, 0.1);

    Particle p1(0.0, 0.0, 0.0, 0.0, 2.0);
    Particle p2(3.0, 0.0, 0.0, 0.0, 1.0);
    Particle p3(0.0, 4.0, 0.0, 0.0, 1.5);
    cpuSim.addParticle(p1); cpuSim.addParticle(p2); cpuSim.addParticle(p3);
    gpuSim.addParticle(p1); gpuSim.addParticle(p2); gpuSim.addParticle(p3);

    cpuSim.computeAccelerations();

    // TODO(gpu): reemplazar por computeAccelerationsGpu()
    gpuSim.computeAccelerations();

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();

    EXPECT_EQ(cpu.size(), gpu.size());
    for (int i = 0; i < N; ++i) {
        SCOPED_TRACE("particula " + std::to_string(i));
        EXPECT_TRUE(compareAccelerations(cpu[i], gpu[i]))
            << "ax=" << cpu[i].getAx() << " vs " << gpu[i].getAx()
            << " ay=" << cpu[i].getAy() << " vs " << gpu[i].getAy();
    }
}

TEST(GpuEquivalence, FullStepN2) {
    const double dt = 0.01;
    NBodySimulator cpuSim(1.0, 0.1);
    NBodySimulator gpuSim(1.0, 0.1);

    Particle p1(0.0, 0.0, 0.5, 0.0, 1.0);
    Particle p2(1.0, 0.0, 0.0, 0.5, 1.0);
    cpuSim.addParticle(p1); cpuSim.addParticle(p2);
    gpuSim.addParticle(p1); gpuSim.addParticle(p2);

    cpuSim.computeAccelerations();
    cpuSim.integrate(dt);

    // TODO(gpu): reemplazar por stepEulerGpu(dt)
    gpuSim.computeAccelerations();
    gpuSim.integrate(dt);

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();

    ASSERT_EQ(cpu.size(), gpu.size());
    for (size_t i = 0; i < cpu.size(); ++i) {
        SCOPED_TRACE("particula " + std::to_string(i));
        EXPECT_TRUE(compareParticles(cpu[i], gpu[i]))
            << mismatchDetail(cpu, gpu);
    }
}

TEST(GpuEquivalence, MultiStepN2) {
    const double dt = 0.01;
    const int steps = 10;
    NBodySimulator cpuSim(1.0, 0.1);
    NBodySimulator gpuSim(1.0, 0.1);

    Particle p1(0.0, 0.0, 0.5, 0.0, 1.0);
    Particle p2(1.0, 0.0, 0.0, 0.5, 1.0);
    cpuSim.addParticle(p1); cpuSim.addParticle(p2);
    gpuSim.addParticle(p1); gpuSim.addParticle(p2);

    for (int step = 0; step < steps; ++step) {
        cpuSim.computeAccelerations();
        cpuSim.integrate(dt);

        // TODO(gpu): reemplazar por stepEulerGpu(dt)
        gpuSim.computeAccelerations();
        gpuSim.integrate(dt);
    }

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();

    ASSERT_EQ(cpu.size(), gpu.size());
    for (size_t i = 0; i < cpu.size(); ++i) {
        SCOPED_TRACE("particula " + std::to_string(i));
        EXPECT_TRUE(compareParticles(cpu[i], gpu[i]))
            << mismatchDetail(cpu, gpu);
    }
}

TEST(GpuEquivalence, RegressionFullSystem) {
    const int N = 200;
    const double dt = 0.01;
    const int steps = 5;

    auto initial = makeTestParticles(N);

    NBodySimulator cpuSim(1.0, 0.1);
    NBodySimulator gpuSim(1.0, 0.1);
    for (const auto& p : initial) { cpuSim.addParticle(p); gpuSim.addParticle(p); }

    for (int step = 0; step < steps; ++step) {
        cpuSim.computeAccelerations();
        cpuSim.integrate(dt);

        // TODO(gpu): reemplazar por stepEulerGpu(dt)
        gpuSim.computeAccelerations();
        gpuSim.integrate(dt);
    }

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();

    ASSERT_EQ(cpu.size(), gpu.size());
    for (size_t i = 0; i < cpu.size(); ++i) {
        SCOPED_TRACE("particula " + std::to_string(i));
        EXPECT_TRUE(compareParticles(cpu[i], gpu[i]))
            << mismatchDetail(cpu, gpu);
    }
}

TEST(GpuEquivalence, EnergyEquivalenceGpu) {
    NBodySimulator cpuSim(1.0, 0.1);
    NBodySimulator gpuSim(1.0, 0.1);

    Particle p1(0.0, 0.0, 0.5, 0.0, 2.0);
    Particle p2(1.0, 0.0, 0.0, 0.5, 1.0);
    cpuSim.addParticle(p1); cpuSim.addParticle(p2);
    gpuSim.addParticle(p1); gpuSim.addParticle(p2);

    cpuSim.computeAccelerations();
    double cpu_K = 0.0, cpu_U = 0.0;
    cpuSim.calculateEnergy(cpu_K, cpu_U);

    // TODO(gpu): reemplazar por calculateEnergyGpu()
    gpuSim.computeAccelerations();
    double gpu_K = 0.0, gpu_U = 0.0;
    gpuSim.calculateEnergy(gpu_K, gpu_U);

    EXPECT_TRUE(compareFloat(cpu_K, gpu_K))
        << "energia cinetica: cpu=" << cpu_K << " gpu=" << gpu_K;
    EXPECT_TRUE(compareFloat(cpu_U, gpu_U))
        << "energia potencial: cpu=" << cpu_U << " gpu=" << gpu_U;
}

TEST(GpuEquivalence, PhysicalInvariantsGpu) {
    const int N = 50;
    const double dt = 0.01;
    auto initial = makeTestParticles(N);

    NBodySimulator cpuSim(1.0, 0.1);
    NBodySimulator gpuSim(1.0, 0.1);
    for (const auto& p : initial) { cpuSim.addParticle(p); gpuSim.addParticle(p); }

    cpuSim.computeAccelerations();
    cpuSim.integrate(dt);

    // TODO(gpu): reemplazar por stepEulerGpu(dt)
    gpuSim.computeAccelerations();
    gpuSim.integrate(dt);

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();

    auto cpu_P = MetricsCalculator::calculateTotalMomentum(cpu);
    auto gpu_P = MetricsCalculator::calculateTotalMomentum(gpu);
    EXPECT_TRUE(compareFloat(cpu_P.first, gpu_P.first))
        << "momento x: cpu=" << cpu_P.first << " gpu=" << gpu_P.first;
    EXPECT_TRUE(compareFloat(cpu_P.second, gpu_P.second))
        << "momento y: cpu=" << cpu_P.second << " gpu=" << gpu_P.second;

    auto cpu_CM = MetricsCalculator::calculateCenterOfMass(cpu);
    auto gpu_CM = MetricsCalculator::calculateCenterOfMass(gpu);
    EXPECT_TRUE(compareFloat(cpu_CM.first, gpu_CM.first))
        << "CM x: cpu=" << cpu_CM.first << " gpu=" << gpu_CM.first;
    EXPECT_TRUE(compareFloat(cpu_CM.second, gpu_CM.second))
        << "CM y: cpu=" << cpu_CM.second << " gpu=" << gpu_CM.second;

    double cpu_rms = MetricsCalculator::calculateRMSRadius(cpu);
    double gpu_rms = MetricsCalculator::calculateRMSRadius(gpu);
    EXPECT_TRUE(compareFloat(cpu_rms, gpu_rms))
        << "radio RMS: cpu=" << cpu_rms << " gpu=" << gpu_rms;
}
