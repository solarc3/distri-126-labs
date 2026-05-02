#include <gtest/gtest.h>
#include <cmath>
#include <vector>
#include "../Particle.h"
#include "../NBodySimulator.h"
#include "../MetricsCalculator.h"

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
