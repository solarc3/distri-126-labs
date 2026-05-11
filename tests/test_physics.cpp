#include <gtest/gtest.h>
#include <cmath>
#include <vector>
#include "../Particle.h"
#include "../NBodySimulator.h"
#include "../MetricsCalculator.h"
#include "../Integrator.h"

TEST(PhysicsTest, AnalyticalForceTwoBodies) {
    NBodySimulator sys(1.0, 0.1);

    Particle p1(0.0, 0.0, 0.0, 0.0, 1.0);
    Particle p2(1.0, 0.0, 0.0, 0.0, 1.0);

    sys.addParticle(p1);
    sys.addParticle(p2);

    sys.computeAccelerations();

    const auto& bodies = sys.getParticles();

    double expected_ax = 1.0 / std::pow(1.01, 1.5);

    EXPECT_NEAR(bodies[0].getAx(), expected_ax, 1e-5);
    EXPECT_NEAR(bodies[1].getAx(), -expected_ax, 1e-5);
}

TEST(PhysicsTest, ActionReaction) {
    NBodySimulator sys(1.0, 0.0);

    Particle p1(0.0, 0.0, 0.0, 0.0, 2.5);
    Particle p2(3.0, 4.0, 0.0, 0.0, 4.0);

    sys.addParticle(p1);
    sys.addParticle(p2);

    sys.computeAccelerations();
    const auto& bodies = sys.getParticles();

    double f1_x = bodies[0].getMass() * bodies[0].getAx();
    double f1_y = bodies[0].getMass() * bodies[0].getAy();

    double f2_x = bodies[1].getMass() * bodies[1].getAx();
    double f2_y = bodies[1].getMass() * bodies[1].getAy();

    EXPECT_NEAR(f1_x, -f2_x, 1e-5);
    EXPECT_NEAR(f1_y, -f2_y, 1e-5);
}

TEST(IntegrationTest, SerialVsParallel) {
    NBodySimulator sysSerial(1.0, 0.1);
    NBodySimulator sysParallel(1.0, 0.1);

    for (int i = 0; i < 100; ++i) {
        Particle p(i * 0.1, i * 0.2, 0.0, 0.0, 1.0);
        sysSerial.addParticle(p);
        sysParallel.addParticle(p);
    }

    sysSerial.computeAccelerations();
    sysParallel.computeAccelerations();

    const auto& bodiesS = sysSerial.getParticles();
    const auto& bodiesP = sysParallel.getParticles();

    for (size_t i = 0; i < bodiesS.size(); ++i) {
        EXPECT_NEAR(bodiesS[i].getAx(), bodiesP[i].getAx(), 1e-9);
        EXPECT_NEAR(bodiesS[i].getAy(), bodiesP[i].getAy(), 1e-9);
    }
}

TEST(RegressionTest, SofteningPreventsSingularity) {
    double epsilon = 0.1;
    NBodySimulator sys(1.0, epsilon);

    Particle p1(0.0, 0.0, 0.0, 0.0, 1.0);
    Particle p2(1e-10, 0.0, 0.0, 0.0, 1.0);

    sys.addParticle(p1);
    sys.addParticle(p2);

    sys.computeAccelerations();
    const auto& bodies = sys.getParticles();

    // Las aceleraciones deben ser finitas (no NaN ni infinito)
    EXPECT_TRUE(std::isfinite(bodies[0].getAx()));
    EXPECT_TRUE(std::isfinite(bodies[0].getAy()));
    EXPECT_TRUE(std::isfinite(bodies[1].getAx()));
    EXPECT_TRUE(std::isfinite(bodies[1].getAy()));
}

TEST(RegressionTest, NonNegativeMass) {
    NBodySimulator sys(1.0, 0.1);

    Particle p1(0.0, 0.0, 0.0, 0.0, 1.0);
    Particle p2(1.0, 0.0, 0.0, 0.0, -0.5);

    sys.addParticle(p1);
    sys.addParticle(p2);

    // No debe crashear al calcular fuerzas con masa negativa
    sys.computeAccelerations();
    const auto& bodies = sys.getParticles();

    // Cada campo debe ser finito
    for (const auto& b : bodies) {
        EXPECT_TRUE(std::isfinite(b.getAx()));
        EXPECT_TRUE(std::isfinite(b.getAy()));
        EXPECT_TRUE(std::isfinite(b.getX()));
        EXPECT_TRUE(std::isfinite(b.getY()));
    }
}

TEST(MetricsCalculatorTest, TotalMomentumConservation) {
    // Dos particulas con velocidades opuestas: momento total debe ser (0, 0)
    std::vector<Particle> particles;
    particles.emplace_back(0.0, 0.0,  1.0, 0.0, 2.0);
    particles.emplace_back(1.0, 0.0, -1.0, 0.0, 2.0);

    auto P = MetricsCalculator::calculateTotalMomentum(particles);
    EXPECT_NEAR(P.first,  0.0, 1e-9);
    EXPECT_NEAR(P.second, 0.0, 1e-9);
}

TEST(MetricsCalculatorTest, CenterOfMass) {
    // Cuatro particulas simetricas: CM debe estar en (0, 0)
    std::vector<Particle> particles;
    particles.emplace_back( 1.0,  1.0, 0.0, 0.0, 1.0);
    particles.emplace_back(-1.0,  1.0, 0.0, 0.0, 1.0);
    particles.emplace_back( 1.0, -1.0, 0.0, 0.0, 1.0);
    particles.emplace_back(-1.0, -1.0, 0.0, 0.0, 1.0);

    auto CM = MetricsCalculator::calculateCenterOfMass(particles);
    EXPECT_NEAR(CM.first,  0.0, 1e-9);
    EXPECT_NEAR(CM.second, 0.0, 1e-9);
}

TEST(MetricsCalculatorTest, CenterOfMassWeighted) {
    // Dos masas diferentes: CM debe ponderar por masa
    std::vector<Particle> particles;
    particles.emplace_back(0.0, 0.0, 0.0, 0.0, 1.0);
    particles.emplace_back(3.0, 4.0, 0.0, 0.0, 2.0);

    auto CM = MetricsCalculator::calculateCenterOfMass(particles);
    // CMx = (1*0 + 2*3) / 3 = 2.0
    // CMy = (1*0 + 2*4) / 3 = 8/3 ≈ 2.666...
    EXPECT_NEAR(CM.first,  2.0, 1e-9);
    EXPECT_NEAR(CM.second, 8.0 / 3.0, 1e-9);
}

TEST(MetricsCalculatorTest, RMSRadius) {
    std::vector<Particle> particles;
    particles.emplace_back( 1.0,  1.0, 0.0, 0.0, 1.0);
    particles.emplace_back(-1.0,  1.0, 0.0, 0.0, 1.0);
    particles.emplace_back( 1.0, -1.0, 0.0, 0.0, 1.0);
    particles.emplace_back(-1.0, -1.0, 0.0, 0.0, 1.0);

    double rms = MetricsCalculator::calculateRMSRadius(particles);
    // Cada particular dista sqrt(2) del CM (0,0)
    // RMS = sqrt( (2+2+2+2) / 4 ) = sqrt(2) ≈ 1.4142
    EXPECT_NEAR(rms, std::sqrt(2.0), 1e-6);
}

TEST(MetricsCalculatorTest, MinDistance) {
    std::vector<Particle> particles;
    particles.emplace_back(0.0, 0.0, 0.0, 0.0, 1.0);
    particles.emplace_back(3.0, 4.0, 0.0, 0.0, 1.0);
    particles.emplace_back(1.0, 0.0, 0.0, 0.0, 1.0);

    double min_dist = MetricsCalculator::calculateMinDistance(particles);
    // Distancia entre (0,0) y (1,0) = 1.0 -> minima
    EXPECT_NEAR(min_dist, 1.0, 1e-9);
}

// --- Tests de equivalencia de sobrecargas OpenMP ---

static std::vector<Particle> makeTestParticles(int n) {
    std::vector<Particle> particles;
    for (int i = 0; i < n; ++i) {
        particles.emplace_back(i * 0.2, i * 0.3 - 1.0, 0.1 + i * 0.01, -0.05 * i, 1.0 + (i % 3) * 0.5);
    }
    return particles;
}

static NBodySimulator makeTestSim(double G = 1.0, double eps = 0.1, int n = 50) {
    NBodySimulator sim(G, eps);
    for (const auto& p : makeTestParticles(n)) sim.addParticle(p);
    return sim;
}

TEST(OpenMPOverloadTest, SchedulesProduceSameResult) {
    auto ref = makeTestSim();
    ref.computeAccelerations();
    const auto& rp = ref.getParticles();

    for (int s = 0; s <= 2; ++s) {
        auto sim = makeTestSim();
        sim.computeAccelerations(s);
        const auto& sp = sim.getParticles();
        for (size_t i = 0; i < sp.size(); ++i) {
            EXPECT_NEAR(rp[i].getAx(), sp[i].getAx(), 1e-9) << "Schedule " << s << " particle " << i;
            EXPECT_NEAR(rp[i].getAy(), sp[i].getAy(), 1e-9) << "Schedule " << s << " particle " << i;
        }
    }
}

TEST(OpenMPOverloadTest, SchedulesWithChunkProduceSameResult) {
    auto ref = makeTestSim();
    ref.computeAccelerations();
    const auto& rp = ref.getParticles();

    for (int s = 0; s <= 2; ++s) {
        for (int chunk : {10, 25}) {
            auto sim = makeTestSim();
            sim.computeAccelerations(s, chunk);
            const auto& sp = sim.getParticles();
            for (size_t i = 0; i < sp.size(); ++i) {
                EXPECT_NEAR(rp[i].getAx(), sp[i].getAx(), 1e-9) << "Sched " << s << " chk " << chunk;
                EXPECT_NEAR(rp[i].getAy(), sp[i].getAy(), 1e-9) << "Sched " << s << " chk " << chunk;
            }
        }
    }
}

TEST(OpenMPOverloadTest, CollapseProducesFiniteResult) {
    auto sim = makeTestSim();
    sim.computeAccelerationsCollapse();
    for (const auto& p : sim.getParticles()) {
        EXPECT_TRUE(std::isfinite(p.getAx()));
        EXPECT_TRUE(std::isfinite(p.getAy()));
    }
}

TEST(OpenMPOverloadTest, Newton3ProducesSameResult) {
    auto ref = makeTestSim(1.0, 0.1, 80);
    ref.computeAccelerations();
    const auto& rp = ref.getParticles();

    auto sim = makeTestSim(1.0, 0.1, 80);
    sim.computeAccelerationsNewton3();
    const auto& sp = sim.getParticles();

    for (size_t i = 0; i < sp.size(); ++i) {
        EXPECT_NEAR(rp[i].getAx(), sp[i].getAx(), 1e-9) << "particle " << i;
        EXPECT_NEAR(rp[i].getAy(), sp[i].getAy(), 1e-9) << "particle " << i;
    }
}

TEST(OpenMPOverloadTest, SoAProducesSameResult) {
    auto ref = makeTestSim(1.0, 0.1, 80);
    ref.computeAccelerations();
    const auto& rp = ref.getParticles();

    auto sim = makeTestSim(1.0, 0.1, 80);
    sim.computeAccelerationsSoA();
    const auto& sp = sim.getParticles();

    for (size_t i = 0; i < sp.size(); ++i) {
        EXPECT_NEAR(rp[i].getAx(), sp[i].getAx(), 1e-9) << "particle " << i;
        EXPECT_NEAR(rp[i].getAy(), sp[i].getAy(), 1e-9) << "particle " << i;
    }
}

TEST(OpenMPOverloadTest, IntegrateSyncTypesProduceSameResult) {
    double dt = 0.01;
    // Referencia: NORMAL
    auto ref = makeTestSim();
    ref.computeAccelerations();
    ref.integrate(dt);
    const auto& rp = ref.getParticles();

    auto compare = [&](int sync_type, const char* name) {
        auto sim = makeTestSim();
        sim.computeAccelerations();
        sim.integrateEuler(dt, sync_type);
        const auto& sp = sim.getParticles();
        for (size_t i = 0; i < sp.size(); ++i) {
            EXPECT_NEAR(rp[i].getX(), sp[i].getX(), 1e-9) << name << " x@" << i;
            EXPECT_NEAR(rp[i].getY(), sp[i].getY(), 1e-9) << name << " y@" << i;
            EXPECT_NEAR(rp[i].getVx(), sp[i].getVx(), 1e-9) << name << " vx@" << i;
            EXPECT_NEAR(rp[i].getVy(), sp[i].getVy(), 1e-9) << name << " vy@" << i;
        }
    };

    compare(0, "ATOMIC");
    compare(1, "CRITICAL");
    compare(2, "NOWAIT");
}

TEST(OpenMPOverloadTest, IntegrateBarrierProducesSameResult) {
    double dt = 0.01;
    auto ref = makeTestSim();
    ref.computeAccelerations();
    ref.integrate(dt);
    const auto& rp = ref.getParticles();

    auto sim = makeTestSim();
    sim.computeAccelerations();
    sim.integrateEuler(dt, 2, true);
    const auto& sp = sim.getParticles();
    for (size_t i = 0; i < sp.size(); ++i) {
        EXPECT_NEAR(rp[i].getX(), sp[i].getX(), 1e-9);
        EXPECT_NEAR(rp[i].getY(), sp[i].getY(), 1e-9);
        EXPECT_NEAR(rp[i].getVx(), sp[i].getVx(), 1e-9);
        EXPECT_NEAR(rp[i].getVy(), sp[i].getVy(), 1e-9);
    }
}

TEST(OpenMPOverloadTest, EnergyMethodsAgree) {
    auto sim = makeTestSim();
    sim.computeAccelerations();

    double k0, p0, k1, p1, k2, p2, k3, p3;
    sim.calculateEnergy(k0, p0);
    sim.calculateEnergy(k1, p1, 0);
    sim.calculateEnergy(k2, p2, 1);
    sim.calculateEnergy(k3, p3, 1, true);

    EXPECT_NEAR(k0, k1, 1e-9);
    EXPECT_NEAR(p0, p1, 1e-9);
    EXPECT_NEAR(k0, k2, 1e-9);
    EXPECT_NEAR(p0, p2, 1e-9);
    EXPECT_NEAR(k0, k3, 1e-9);
    EXPECT_NEAR(p0, p3, 1e-9);
}

TEST(OpenMPOverloadTest, DemoMethodsDontCrash) {
    auto sim = makeTestSim(1.0, 0.1, 30);
    sim.computeAccelerations();

    EXPECT_NO_THROW(sim.processBodies());
    EXPECT_NO_THROW(sim.processBodies(0));
    EXPECT_NO_THROW(sim.processBodies(1));
    EXPECT_NO_THROW(sim.processBodies(0, true));
    EXPECT_NO_THROW(sim.simulatePhasesBarrier());
    EXPECT_NO_THROW(sim.parallelInitializationSingle());

    double m = sim.calculateMetricsFirstprivate();
    EXPECT_GT(m, 0.0);

    Particle last = sim.calculateFinalStateLastprivate();
    EXPECT_GT(last.getMass(), 0.0);
}

TEST(OpenMPOverloadTest, LastprivateReturnsLastParticle) {
    auto sim = makeTestSim(1.0, 0.1, 20);
    const auto& parts = sim.getParticles();
    ASSERT_GT(parts.size(), 0u);
    Particle expected_last = parts.back();

    Particle result = sim.calculateFinalStateLastprivate();
    EXPECT_DOUBLE_EQ(expected_last.getX(), result.getX());
    EXPECT_DOUBLE_EQ(expected_last.getY(), result.getY());
    EXPECT_DOUBLE_EQ(expected_last.getMass(), result.getMass());
}
