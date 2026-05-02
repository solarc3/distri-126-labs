#include <gtest/gtest.h>
#include <cmath>
#include "../Particle.h"
#include "../NBodySimulator.h"

// test de fuerza 2 cuerpos fijos
TEST(PhysicsTest, AnalyticalForceTwoBodies) {
    // G = 1.0, epsilon = 0.1
    NBodySimulator sys(1.0, 0.1); 
    
    // masa 1 en origen, masa 2 en x = 1.0
    Particle p1(0.0, 0.0, 0.0, 0.0, 1.0);
    Particle p2(1.0, 0.0, 0.0, 0.0, 1.0);
    
    sys.addParticle(p1);
    sys.addParticle(p2);
    
    sys.computeAccelerations();
    
    const auto& bodies = sys.getParticles();
    
    // ccalculo para epsilon = 0.1
    // a = G * m2 * d / (d^2 + eps^2)^(3/2) = 1 * 1 * 1 / (1 + 0.01)^(3/2) = 0.98518
    double expected_ax = 1.0 / std::pow(1.01, 1.5);
    
    EXPECT_NEAR(bodies[0].getAx(), expected_ax, 1e-5);
    EXPECT_NEAR(bodies[1].getAx(), -expected_ax, 1e-5);
}

// test de accion-reaccion F_ij = -F_ji 
TEST(PhysicsTest, ActionReaction) {
    NBodySimulator sys(1.0, 0.0); // G = 1, epsilon = 0
    
    Particle p1(0.0, 0.0, 0.0, 0.0, 2.5);
    Particle p2(3.0, 4.0, 0.0, 0.0, 4.0); // distancia = 5
    
    sys.addParticle(p1);
    sys.addParticle(p2);
    
    sys.computeAccelerations();
    const auto& bodies = sys.getParticles();
    
    // F = m * a --> verificar que m1 * a1 == -(m2 * a2)
    double f1_x = bodies[0].getMass() * bodies[0].getAx();
    double f1_y = bodies[0].getMass() * bodies[0].getAy();
    
    double f2_x = bodies[1].getMass() * bodies[1].getAx();
    double f2_y = bodies[1].getMass() * bodies[1].getAy();
    
    EXPECT_NEAR(f1_x, -f2_x, 1e-5);
    EXPECT_NEAR(f1_y, -f2_y, 1e-5);
}

// test de integracion 
TEST(IntegrationTest, SerialVsParallel) {
    NBodySimulator sysSerial(1.0, 0.1);
    NBodySimulator sysParallel(1.0, 0.1);
    
    // inicializar con mismas semillas
    for(int i = 0; i < 100; ++i) {
        Particle p(i * 0.1, i * 0.2, 0.0, 0.0, 1.0); // dummy
        sysSerial.addParticle(p);
        sysParallel.addParticle(p);
    }
    
    sysSerial.computeAccelerations(); 
    sysParallel.computeAccelerations(); 
    
    const auto& bodiesS = sysSerial.getParticles();
    const auto& bodiesP = sysParallel.getParticles();
    
    for(size_t i = 0; i < bodiesS.size(); ++i) {
        EXPECT_NEAR(bodiesS[i].getAx(), bodiesP[i].getAx(), 1e-9);
        EXPECT_NEAR(bodiesS[i].getAy(), bodiesP[i].getAy(), 1e-9);
    }
}