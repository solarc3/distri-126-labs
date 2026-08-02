#include <gtest/gtest.h>
#include <cmath>
#include <vector>
#include <string>
#include "gpu_test_helpers.h"
#include "cpu_gpu_harness.h"
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
    EXPECT_TRUE(compareFloat(0.0, 1e-9));
    EXPECT_TRUE(compareFloat(0.0, kGpuAtol));
    EXPECT_TRUE(compareFloat(0.0, -5e-9));
}

TEST(GpuTestHarness, CompareFloatWithinRtol) {
    EXPECT_TRUE(compareFloat(1.0, 1.0 + 5e-5));
    EXPECT_TRUE(compareFloat(1000.0, 1000.0 * (1.0 + kGpuRtol)));
    EXPECT_TRUE(compareFloat(-50.0, -50.0 + 1e-4 * 50.0));
}

TEST(GpuTestHarness, CompareFloatOutsideTolerance) {
    EXPECT_FALSE(compareFloat(1.0, 1.0 + 2e-4));
    EXPECT_FALSE(compareFloat(0.0, 2e-8));
    EXPECT_FALSE(compareFloat(100.0, 100.0 + 0.1));
}

TEST(GpuTestHarness, CompareFloatMixedSigns) {
    EXPECT_FALSE(compareFloat(1.0, -1.0));
    EXPECT_TRUE(compareFloat(1e-10, -1e-10));
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
// Tests de equivalencia CPU vs GPU usando el harness
// ---------------------------------------------------------------------------
// NOTA: Las funciones computeAccelerationsGpu(), computeStepGpu() y
// calculateEnergyGpu() estan marcadas con TODO(gpu) en cpu_gpu_harness.h.
// Actualmente delegan en la implementacion CPU. Cuando R1/R2 entreguen los
// kernels CUDA, solo hay que reemplazar los cuerpos de esas funciones en
// cpu_gpu_harness.h sin modificar los tests.

TEST(GpuEquivalence, AccelerationsN2) {
    HarnessConfig cfg;
    cfg.numBodies = 2;
    cfg.seed = 100;

    auto r = compareAccelerationsOnly(cfg);
    EXPECT_TRUE(r.accelerationsOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

TEST(GpuEquivalence, AccelerationsN3) {
    HarnessConfig cfg;
    cfg.numBodies = 3;
    cfg.seed = 200;

    auto r = compareAccelerationsOnly(cfg);
    EXPECT_TRUE(r.accelerationsOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

TEST(GpuEquivalence, FullStepN2) {
    HarnessConfig cfg;
    cfg.numBodies = 2;
    cfg.seed = 300;
    cfg.dt = 0.01;

    auto r = compareFullStep(cfg);
    EXPECT_TRUE(r.allOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

TEST(GpuEquivalence, MultiStepN2) {
    HarnessConfig cfg;
    cfg.numBodies = 2;
    cfg.seed = 400;
    cfg.dt = 0.01;
    cfg.steps = 10;

    auto r = compareMultiStep(cfg);
    EXPECT_TRUE(r.allOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

TEST(GpuEquivalence, RegressionFullSystem) {
    HarnessConfig cfg;
    cfg.numBodies = 200;
    cfg.seed = 500;
    cfg.dt = 0.01;
    cfg.steps = 5;

    auto r = compareMultiStep(cfg);
    EXPECT_TRUE(r.allOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

TEST(GpuEquivalence, EnergyEquivalenceGpu) {
    HarnessConfig cfg;
    cfg.numBodies = 2;
    cfg.seed = 600;

    auto r = compareEnergy(cfg);
    EXPECT_TRUE(r.allOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

TEST(GpuEquivalence, PhysicalInvariantsGpu) {
    HarnessConfig cfg;
    cfg.numBodies = 50;
    cfg.seed = 700;
    cfg.dt = 0.01;

    auto r = comparePhysicalInvariants(cfg);
    EXPECT_TRUE(r.allOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

// ---------------------------------------------------------------------------
// Tests parametrizados: barrido de N (demuestra modularidad del harness)
// ---------------------------------------------------------------------------

class GpuEquivalenceParameterized : public ::testing::TestWithParam<int> {};

TEST_P(GpuEquivalenceParameterized, AccelerationsScale) {
    int N = GetParam();
    HarnessConfig cfg;
    cfg.numBodies = N;
    cfg.seed = 42;

    auto r = compareAccelerationsOnly(cfg);
    EXPECT_TRUE(r.accelerationsOk) << "N=" << N << ": " << r.firstMismatch;
}

TEST_P(GpuEquivalenceParameterized, MultiStepScale) {
    int N = GetParam();
    HarnessConfig cfg;
    cfg.numBodies = N;
    cfg.seed = 43;
    cfg.dt = 0.01;
    cfg.steps = 3;

    auto r = compareMultiStep(cfg);
    EXPECT_TRUE(r.allOk) << "N=" << N << ": " << r.firstMismatch;
}

INSTANTIATE_TEST_SUITE_P(
    SweepN,
    GpuEquivalenceParameterized,
    ::testing::Values(2, 3, 4, 5, 10, 50, 100, 200)
);

// ---------------------------------------------------------------------------
// Test de consistencia interna del harness: configs distintos deben dar
// resultados distintos (sanity check de inicializacion reproducible)
// ---------------------------------------------------------------------------

TEST(HarnessConsistency, DifferentSeedsProduceDifferentStates) {
    HarnessConfig cfgA;
    cfgA.numBodies = 10;
    cfgA.seed = 1000;

    HarnessConfig cfgB;
    cfgB.numBodies = 10;
    cfgB.seed = 2000;

    NBodySimulator simA(cfgA.G, cfgA.epsilon);
    NBodySimulator simB(cfgB.G, cfgB.epsilon);

    simA.initializeRandom(cfgA.numBodies, cfgA.seed,
                          cfgA.posMin, cfgA.posMax,
                          cfgA.velMin, cfgA.velMax,
                          cfgA.massMin, cfgA.massMax);
    simB.initializeRandom(cfgB.numBodies, cfgB.seed,
                          cfgB.posMin, cfgB.posMax,
                          cfgB.velMin, cfgB.velMax,
                          cfgB.massMin, cfgB.massMax);

    const auto& pA = simA.getParticles();
    const auto& pB = simB.getParticles();
    ASSERT_EQ(pA.size(), pB.size());

    bool anyDifferent = false;
    for (size_t i = 0; i < pA.size(); ++i) {
        if (pA[i].getX() != pB[i].getX() ||
            pA[i].getY() != pB[i].getY() ||
            pA[i].getVx() != pB[i].getVx() ||
            pA[i].getVy() != pB[i].getVy() ||
            pA[i].getMass() != pB[i].getMass()) {
            anyDifferent = true;
            break;
        }
    }
    EXPECT_TRUE(anyDifferent) << "Semillas distintas deberian generar estados distintos";
}

TEST(HarnessConsistency, SameSeedProducesIdenticalStates) {
    HarnessConfig cfg;
    cfg.numBodies = 10;
    cfg.seed = 5000;

    NBodySimulator simA(cfg.G, cfg.epsilon);
    NBodySimulator simB(cfg.G, cfg.epsilon);

    simA.initializeRandom(cfg.numBodies, cfg.seed,
                          cfg.posMin, cfg.posMax,
                          cfg.velMin, cfg.velMax,
                          cfg.massMin, cfg.massMax);
    simB.initializeRandom(cfg.numBodies, cfg.seed,
                          cfg.posMin, cfg.posMax,
                          cfg.velMin, cfg.velMax,
                          cfg.massMin, cfg.massMax);

    const auto& pA = simA.getParticles();
    const auto& pB = simB.getParticles();
    ASSERT_EQ(pA.size(), pB.size());

    for (size_t i = 0; i < pA.size(); ++i) {
        EXPECT_DOUBLE_EQ(pA[i].getX(), pB[i].getX());
        EXPECT_DOUBLE_EQ(pA[i].getY(), pB[i].getY());
        EXPECT_DOUBLE_EQ(pA[i].getVx(), pB[i].getVx());
        EXPECT_DOUBLE_EQ(pA[i].getVy(), pB[i].getVy());
        EXPECT_DOUBLE_EQ(pA[i].getMass(), pB[i].getMass());
    }
}
