#include <gtest/gtest.h>
#include <cmath>
#include <stdexcept>
#include <vector>
#include <string>
#include <tuple>
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
// NOTA: Las funciones computeAccelerationsGpu(), stepEulerGpu() y
// calculateEnergyGpu() ya estan implementadas en NBodySimulator y
// delegadas desde cpu_gpu_harness.h.
// calculateEnergyGpu() soporta method=0 (shared memory) y method=1 (atomic).

TEST(GpuEquivalence, AccelerationsN2) {
    SKIP_IF_NO_GPU();
    HarnessConfig cfg;
    cfg.numBodies = 2;
    cfg.seed = 100;

    auto r = compareAccelerationsOnly(cfg);
    EXPECT_TRUE(r.accelerationsOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

TEST(GpuEquivalence, AccelerationsN3) {
    SKIP_IF_NO_GPU();
    HarnessConfig cfg;
    cfg.numBodies = 3;
    cfg.seed = 200;

    auto r = compareAccelerationsOnly(cfg);
    EXPECT_TRUE(r.accelerationsOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

TEST(GpuEquivalence, FullStepN2) {
    SKIP_IF_NO_GPU();
    HarnessConfig cfg;
    cfg.numBodies = 2;
    cfg.seed = 300;
    cfg.dt = 0.01;

    auto r = compareFullStep(cfg);
    EXPECT_TRUE(r.allOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

TEST(GpuEquivalence, MultiStepN2) {
    SKIP_IF_NO_GPU();
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
    SKIP_IF_NO_GPU();
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
    SKIP_IF_NO_GPU();
    HarnessConfig cfg;
    cfg.numBodies = 2;
    cfg.seed = 600;

    auto r = compareEnergy(cfg);
    EXPECT_TRUE(r.allOk) << r.firstMismatch;
    EXPECT_EQ(r.mismatchCount, 0u);
}

TEST(GpuEquivalence, EnergyMethod1VsMethod0) {
    SKIP_IF_NO_GPU();
    const int N = 100;
    NBodySimulator sim(1.0, 0.1);
    sim.initializeRandom(N, 800, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);

    double k0 = 0.0, u0 = 0.0;
    double k1 = 0.0, u1 = 0.0;

    sim.calculateEnergyGpu(k0, u0, 0);
    sim.calculateEnergyGpu(k1, u1, 1);

    EXPECT_TRUE(compareFloat(k0, k1)) << "K: method0=" << k0 << " method1=" << k1;
    EXPECT_TRUE(compareFloat(u0, u1)) << "U: method0=" << u0 << " method1=" << u1;
}

TEST(GpuEquivalence, EnergyAtomicVsCpu) {
    SKIP_IF_NO_GPU();
    const int N = 100;
    NBodySimulator sim(1.0, 0.1);
    sim.initializeRandom(N, 900, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);

    double cpuK = 0.0, cpuU = 0.0;
    double gpuK = 0.0, gpuU = 0.0;

    sim.calculateEnergy(cpuK, cpuU);
    sim.calculateEnergyGpu(gpuK, gpuU, 1);

    EXPECT_TRUE(compareFloat(cpuK, gpuK))
        << "K cpu=" << cpuK << " gpu(atomic)=" << gpuK;
    EXPECT_TRUE(compareFloat(cpuU, gpuU))
        << "U cpu=" << cpuU << " gpu(atomic)=" << gpuU;
}

TEST(GpuEquivalence, EnergyEmptySystemReturnsZero) {
    SKIP_IF_NO_GPU();
    NBodySimulator sim(1.0, 0.1);

    double k0 = 0.0, u0 = 0.0;
    double k1 = 0.0, u1 = 0.0;

    sim.calculateEnergyGpu(k0, u0, 0);
    EXPECT_DOUBLE_EQ(k0, 0.0);
    EXPECT_DOUBLE_EQ(u0, 0.0);

    sim.calculateEnergyGpu(k1, u1, 1);
    EXPECT_DOUBLE_EQ(k1, 0.0);
    EXPECT_DOUBLE_EQ(u1, 0.0);
}

#if defined(NBODY_ENABLE_CUDA_KERNELS)
TEST(GpuEquivalence, EnergyInvalidMethodThrows) {
    SKIP_IF_NO_GPU();
    const int N = 10;
    NBodySimulator sim(1.0, 0.1);
    sim.initializeRandom(N, 1000, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);

    double k = 0.0, u = 0.0;
    EXPECT_THROW(sim.calculateEnergyGpu(k, u, 999), std::runtime_error);
}
#endif

// ---------------------------------------------------------------------------
// Multi-GPU: getGpuDeviceCount/setGpuDeviceLimit.
// En esta maquina de CI/dev solo hay 0 o 1 GPU fisica disponible, asi que
// estos tests validan el caso de compatibilidad (equivalente a
// i_begin=0, i_count=n de un solo device) y la API publica en si. La ruta
// con N>=2 devices reales no se puede ejercitar sin hardware multi-GPU,
// pero comparte el mismo codigo (splitParticleRange + loop por device) que
// ya esta cubierto por los tests puros en test_gpu_device_split.cpp.
// ---------------------------------------------------------------------------

TEST(GpuMultiDevice, GetGpuDeviceCountNeverNegative) {
    NBodySimulator sim(1.0, 0.1);
    EXPECT_GE(sim.getGpuDeviceCount(), 0);
}

TEST(GpuMultiDevice, SetGpuDeviceLimitClampsCount) {
    NBodySimulator sim(1.0, 0.1);
    const int detected = sim.getGpuDeviceCount();

    sim.setGpuDeviceLimit(0);
    EXPECT_EQ(sim.getGpuDeviceCount(), 0);

    sim.setGpuDeviceLimit(-1);
    EXPECT_EQ(sim.getGpuDeviceCount(), detected);
}

TEST(GpuMultiDevice, DeviceLimitOneMatchesDefaultResult) {
    SKIP_IF_NO_GPU();
    // Fuerza explicitamente el camino de 1 solo device (equivalente al
    // comportamiento previo a este feature: i_begin=0, i_count=n) y lo
    // compara contra CPU, igual que los tests de equivalencia de arriba.
    const int N = 129;
    NBodySimulator sim(1.0, 0.1);
    NBodySimulator cpuSim(1.0, 0.1);
    sim.setGpuDeviceLimit(1);

    sim.initializeRandom(N, 4242, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);
    cpuSim.initializeRandom(N, 4242, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);

    sim.computeAccelerationsGpu(0, 128);
    cpuSim.computeAccelerations();

    const auto& gpu = sim.getParticles();
    const auto& cpu = cpuSim.getParticles();
    ASSERT_EQ(gpu.size(), cpu.size());
    for (size_t i = 0; i < gpu.size(); ++i) {
        EXPECT_TRUE(compareAccelerations(gpu[i], cpu[i])) << "i=" << i;
    }
}

TEST(GpuMultiDevice, DeviceLimitOneEnergyMatchesCpu) {
    SKIP_IF_NO_GPU();
    const int N = 64;
    NBodySimulator sim(1.0, 0.1);
    sim.setGpuDeviceLimit(1);
    sim.initializeRandom(N, 4343, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);

    double gpuK = 0.0, gpuU = 0.0, cpuK = 0.0, cpuU = 0.0;
    sim.calculateEnergyGpu(gpuK, gpuU, 0);
    sim.calculateEnergy(cpuK, cpuU);

    EXPECT_TRUE(compareFloat(cpuK, gpuK));
    EXPECT_TRUE(compareFloat(cpuU, gpuU));
}

// ---------------------------------------------------------------------------
// Tests analiticos: aceleracion contra valor conocido (sin seed random).
// Requisito del laboratorio: "aceleracion entre 2-3 cuerpos CPU vs analitico".
// ---------------------------------------------------------------------------

TEST(GpuEquivalence, AnalyticalTwoBodies) {
    SKIP_IF_NO_GPU();
    // m1 en (0,0), m2 en (1,0). G=m1=m2=1, eps=0.1.
    // a1x = G * m2 / (dx^2 + eps^2)^(3/2)
    //     = 1 / (1 + 0.01)^1.5 = 1 / 1.01^1.5
    const double G = 1.0;
    const double eps = 0.1;
    const double dx = 1.0;
    const double expected_a1x = G * 1.0 * dx / std::pow(dx * dx + eps * eps, 1.5);
    const double expected_a2x = -expected_a1x;

    NBodySimulator cpuSim(G, eps);
    NBodySimulator gpuSim0(G, eps);
    NBodySimulator gpuSim1(G, eps);

    Particle p1(0.0, 0.0, 0.0, 0.0, 1.0);
    Particle p2(1.0, 0.0, 0.0, 0.0, 1.0);

    cpuSim.addParticle(p1); cpuSim.addParticle(p2);
    gpuSim0.addParticle(p1); gpuSim0.addParticle(p2);
    gpuSim1.addParticle(p1); gpuSim1.addParticle(p2);

    cpuSim.computeAccelerations();
    gpuSim0.computeAccelerationsGpu(0, 256);
    gpuSim1.computeAccelerationsGpu(1, 256);

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu0 = gpuSim0.getParticles();
    const auto& gpu1 = gpuSim1.getParticles();

    EXPECT_NEAR(cpu[0].getAx(), expected_a1x, 1e-15);
    EXPECT_NEAR(cpu[0].getAy(), 0.0, 1e-15);
    EXPECT_NEAR(cpu[1].getAx(), expected_a2x, 1e-15);
    EXPECT_NEAR(cpu[1].getAy(), 0.0, 1e-15);

    EXPECT_TRUE(compareAccelerations(gpu0[0], cpu[0]))
        << "gpu variant=0 vs cpu";
    EXPECT_TRUE(compareAccelerations(gpu1[0], cpu[0]))
        << "gpu variant=1 vs cpu";
}

TEST(GpuEquivalence, AnalyticalThreeBodies) {
    SKIP_IF_NO_GPU();
    // m1(0,0) m2(1,0) m3(0,1), G=mi=1, eps=0.1.
    // a1: contribucion de m2 en +x, de m3 en +y → magnitudes iguales
    // a2: contribucion de m1 en -x, de m3 en (-1,+1)
    // a3: contribucion de m1 en -y, de m2 en (+1,-1)
    const double G = 1.0;
    const double eps = 0.1;

    // distancia unitaria (dx=1,dy=0 o dx=0,dy=1): r2 = 1 + 0.01
    const double s1 = 1.0 / std::pow(1.0 + eps * eps, 1.5);
    // distancia diagonal (dx=1,dy=1): r2 = 2 + 0.01
    const double s2 = 1.0 / std::pow(2.0 + eps * eps, 1.5);

    const double a1x = s1;          // m2 aporta +x
    const double a1y = s1;          // m3 aporta +y
    const double a2x = -s1 - s2;    // m1: -x, m3: dx=-1
    const double a2y = s2;          // m3: dy=+1
    const double a3x = s2;          // m2: dx=+1
    const double a3y = -s1 - s2;    // m1: -y, m2: dy=-1

    NBodySimulator cpuSim(G, eps);
    NBodySimulator gpuSim0(G, eps);
    NBodySimulator gpuSim1(G, eps);

    Particle p1(0.0, 0.0, 0.0, 0.0, 1.0);
    Particle p2(1.0, 0.0, 0.0, 0.0, 1.0);
    Particle p3(0.0, 1.0, 0.0, 0.0, 1.0);

    cpuSim.addParticle(p1); cpuSim.addParticle(p2); cpuSim.addParticle(p3);
    gpuSim0.addParticle(p1); gpuSim0.addParticle(p2); gpuSim0.addParticle(p3);
    gpuSim1.addParticle(p1); gpuSim1.addParticle(p2); gpuSim1.addParticle(p3);

    cpuSim.computeAccelerations();
    gpuSim0.computeAccelerationsGpu(0, 256);
    gpuSim1.computeAccelerationsGpu(1, 256);

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu0 = gpuSim0.getParticles();
    const auto& gpu1 = gpuSim1.getParticles();

    // CPU vs analitico
    EXPECT_NEAR(cpu[0].getAx(), a1x, 1e-15) << "cpu body0 ax";
    EXPECT_NEAR(cpu[0].getAy(), a1y, 1e-15) << "cpu body0 ay";
    EXPECT_NEAR(cpu[1].getAx(), a2x, 1e-15) << "cpu body1 ax";
    EXPECT_NEAR(cpu[1].getAy(), a2y, 1e-15) << "cpu body1 ay";
    EXPECT_NEAR(cpu[2].getAx(), a3x, 1e-15) << "cpu body2 ax";
    EXPECT_NEAR(cpu[2].getAy(), a3y, 1e-15) << "cpu body2 ay";

    // GPU vs analitico (tolerancia GPU por rsqrt)
    for (size_t i = 0; i < 3; ++i) {
        EXPECT_TRUE(compareAccelerations(gpu0[i], cpu[i]))
            << "gpu variant=0 body" << i;
        EXPECT_TRUE(compareAccelerations(gpu1[i], cpu[i]))
            << "gpu variant=1 body" << i;
    }
}

TEST(GpuEquivalence, PhysicalInvariantsGpu) {
    SKIP_IF_NO_GPU();
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
    SKIP_IF_NO_GPU();
    int N = GetParam();
    HarnessConfig cfg;
    cfg.numBodies = N;
    cfg.seed = 42;

    auto r = compareAccelerationsOnly(cfg);
    EXPECT_TRUE(r.accelerationsOk) << "N=" << N << ": " << r.firstMismatch;
}

TEST_P(GpuEquivalenceParameterized, MultiStepScale) {
    SKIP_IF_NO_GPU();
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
    ::testing::Values(2, 3, 4, 5, 10, 50, 100, 200, 257, 512, 1000, 2000)
);

// ---------------------------------------------------------------------------
// Tests de cobertura de block_size y variant en computeAccelerationsGpu
// Usan ::testing::Combine para barrer todas las combinaciones de
// (N, block_size, variant).
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Test GPU vs CPU para todas las combinaciones de (N, block_size, variant).
// Cubre invariancia: mismo N, distinto block_size o variant debe producir
// el mismo resultado que CPU dentro de tolerancia.
// ---------------------------------------------------------------------------

class GpuBlockSizeVariantVsCpu
    : public ::testing::TestWithParam<std::tuple<int, int, int>> {};

TEST_P(GpuBlockSizeVariantVsCpu, AccelerationsMatchCpu) {
    SKIP_IF_NO_GPU();
    int N = std::get<0>(GetParam());
    int block_size = std::get<1>(GetParam());
    int variant = std::get<2>(GetParam());

    unsigned int seed = static_cast<unsigned int>(N * 1000 + block_size + variant * 777);
    NBodySimulator cpuSim(1.0, 0.1);
    NBodySimulator gpuSim(1.0, 0.1);

    cpuSim.initializeRandom(N, seed, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);
    gpuSim.initializeRandom(N, seed, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);

    cpuSim.computeAccelerations();
    gpuSim.computeAccelerationsGpu(variant, block_size);

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu = gpuSim.getParticles();
    ASSERT_EQ(cpu.size(), gpu.size());

    for (size_t i = 0; i < cpu.size(); ++i) {
        EXPECT_TRUE(compareAccelerations(cpu[i], gpu[i]))
            << "N=" << N << " block=" << block_size
            << " variant=" << variant << " i=" << i;
    }
}

INSTANTIATE_TEST_SUITE_P(
    SweepBlockSizeVariant,
    GpuBlockSizeVariantVsCpu,
    ::testing::Combine(
        ::testing::Values(50, 65, 129, 257, 513, 1025),
        ::testing::Values(64, 128, 256, 512, 1024),
        ::testing::Values(0, 1)
    )
);

// ---------------------------------------------------------------------------
// Test equivalencia variant=0 vs variant=1 directa (sin pasar por CPU).
// N que cruzan bordes de bloque para todos los block_size.
// ---------------------------------------------------------------------------

class GpuAccelerationsVariantEquivalence
    : public ::testing::TestWithParam<std::tuple<int, int>> {};

TEST_P(GpuAccelerationsVariantEquivalence, Variant0VsVariant1) {
    SKIP_IF_NO_GPU();
    int N = std::get<0>(GetParam());
    int block_size = std::get<1>(GetParam());

    unsigned int seed = static_cast<unsigned int>(N * 2000 + block_size + 5000);
    NBodySimulator sim0(1.0, 0.1);
    NBodySimulator sim1(1.0, 0.1);

    sim0.initializeRandom(N, seed, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);
    sim1.initializeRandom(N, seed, -10.0, 10.0, -1.0, 1.0, 0.5, 2.0);

    sim0.computeAccelerationsGpu(0, block_size);
    sim1.computeAccelerationsGpu(1, block_size);

    const auto& p0 = sim0.getParticles();
    const auto& p1 = sim1.getParticles();
    ASSERT_EQ(p0.size(), p1.size());

    for (size_t i = 0; i < p0.size(); ++i) {
        EXPECT_TRUE(compareAccelerations(p0[i], p1[i]))
            << "N=" << N << " block=" << block_size << " i=" << i;
    }
}

INSTANTIATE_TEST_SUITE_P(
    SweepVariantEquiv,
    GpuAccelerationsVariantEquivalence,
    ::testing::Combine(
        ::testing::Values(50, 65, 129, 257, 513, 1025),
        ::testing::Values(64, 128, 256, 512, 1024)
    )
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
            pA[i].getAx() != pB[i].getAx() ||
            pA[i].getAy() != pB[i].getAy() ||
            pA[i].getMass() != pB[i].getMass()) {
            anyDifferent = true;
            break;
        }
    }
    EXPECT_TRUE(anyDifferent) << "Different seeds should produce different states";
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
        EXPECT_DOUBLE_EQ(pA[i].getAx(), pB[i].getAx());
        EXPECT_DOUBLE_EQ(pA[i].getAy(), pB[i].getAy());
        EXPECT_DOUBLE_EQ(pA[i].getMass(), pB[i].getMass());
    }
}

// ---------------------------------------------------------------------------
// Regresion: eps == 0 con lanes de padding en el kernel de shared memory.
// Los lanes con j >= n se rellenan con ceros; si la particula i esta en el
// origen exacto, r2 = xi^2 + yi^2 = 0 -> rsqrt(0) = inf -> 0.0 * inf = NaN.
// Requiere N no multiplo de block_size para que exista un tile parcial.
// ---------------------------------------------------------------------------

class GpuZeroSofteningPadding
    : public ::testing::TestWithParam<std::tuple<int, int>> {};

TEST_P(GpuZeroSofteningPadding, NoNaNAndVariantsMatch) {
    SKIP_IF_NO_GPU();
    const int N = std::get<0>(GetParam());
    const int block_size = std::get<1>(GetParam());
    ASSERT_NE(N % block_size, 0) << "el test necesita un tile parcial";

    // epsilon = 0: sin suavizado, la autointeraccion se salta por indice.
    NBodySimulator cpuSim(1.0, 0.0);
    NBodySimulator gpuSim0(1.0, 0.0);
    NBodySimulator gpuSim1(1.0, 0.0);

    // Particula 0 exactamente en el origen; el resto en posiciones distintas
    // para no crear singularidades reales entre pares.
    for (int i = 0; i < N; ++i) {
        Particle p(i == 0 ? 0.0 : 1.0 + i * 0.5,
                   i == 0 ? 0.0 : -2.0 + i * 0.25,
                   0.0, 0.0,
                   1.0 + (i % 3) * 0.5);
        cpuSim.addParticle(p);
        gpuSim0.addParticle(p);
        gpuSim1.addParticle(p);
    }

    cpuSim.computeAccelerations();
    gpuSim0.computeAccelerationsGpu(0, block_size);
    gpuSim1.computeAccelerationsGpu(1, block_size);

    const auto& cpu = cpuSim.getParticles();
    const auto& gpu0 = gpuSim0.getParticles();
    const auto& gpu1 = gpuSim1.getParticles();
    ASSERT_EQ(cpu.size(), gpu1.size());

    for (size_t i = 0; i < gpu1.size(); ++i) {
        EXPECT_TRUE(std::isfinite(gpu1[i].getAx()))
            << "N=" << N << " block=" << block_size << " i=" << i << " ax no finito";
        EXPECT_TRUE(std::isfinite(gpu1[i].getAy()))
            << "N=" << N << " block=" << block_size << " i=" << i << " ay no finito";

        EXPECT_TRUE(compareAccelerations(gpu1[i], gpu0[i]))
            << "variant1 vs variant0, N=" << N << " block=" << block_size << " i=" << i;
        EXPECT_TRUE(compareAccelerations(gpu1[i], cpu[i]))
            << "variant1 vs cpu, N=" << N << " block=" << block_size << " i=" << i;
    }
}

INSTANTIATE_TEST_SUITE_P(
    ZeroSofteningPadding,
    GpuZeroSofteningPadding,
    ::testing::Combine(
        ::testing::Values(2, 3, 70, 130, 257),
        ::testing::Values(64, 256)
    )
);
