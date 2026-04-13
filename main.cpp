#include <iostream>
#include <cmath>
#include "Particle.h"
#include "NBodySystem.h"

// Colores para output
#define GREEN "\033[32m"
#define RED   "\033[31m"
#define RESET "\033[0m"

void testEjemploEnunciado() {
    std::cout << "=== Test: Ejemplo numerico del enunciado ===" << std::endl;
    std::cout << "Dos masas en eje x: m1 en x=0, m2 en x=1" << std::endl;
    std::cout << "G=1, m2=1, d=1, epsilon=0.1" << std::endl;
    std::cout << "Esperado: a1_x ~ 0.985 (dirigida hacia +x)" << std::endl;

    NBodySystem sys(1.0, 0.1);
    sys.addParticle(Particle(1.0, 0.0, 0.0)); // m1 en x=0
    sys.addParticle(Particle(1.0, 1.0, 0.0)); // m2 en x=1

    sys.computeAccelerations();

    auto& particles = sys.getParticles();
    double ax1 = particles[0].getAx();
    double ay1 = particles[0].getAy();
    double ax2 = particles[1].getAx();
    double ay2 = particles[1].getAy();

    std::cout << "\nResultados:" << std::endl;
    std::cout << "  Particula 1: ax=" << ax1 << " ay=" << ay1 << std::endl;
    std::cout << "  Particula 2: ax=" << ax2 << " ay=" << ay2 << std::endl;

    // Verificaciones
    double tolerancia = 1e-6;
    bool ok = true;

    // a1_x debe ser positiva (atraida hacia m2 en +x)
    if (ax1 <= 0) {
        std::cout << RED << "  [FAIL] a1_x deberia ser positiva" << RESET << std::endl;
        ok = false;
    }

    // a2_x debe ser negativa (atraida hacia m1 en -x)
    if (ax2 >= 0) {
        std::cout << RED << "  [FAIL] a2_x deberia ser negativa" << RESET << std::endl;
        ok = false;
    }

    // Accion-reaccion: m1*a1 = -m2*a2 (mismas masas -> a1 = -a2)
    if (std::abs(ax1 + ax2) > tolerancia) {
        std::cout << RED << "  [FAIL] Accion-reaccion violada: ax1+ax2=" 
                  << ax1+ax2 << RESET << std::endl;
        ok = false;
    }

    // Componente y debe ser ~0 (ambas en eje x)
    if (std::abs(ay1) > tolerancia || std::abs(ay2) > tolerancia) {
        std::cout << RED << "  [FAIL] Componente y deberia ser 0" << RESET << std::endl;
        ok = false;
    }

    if (ok) {
        std::cout << GREEN << "  [PASS] Todos los checks pasaron" << RESET << std::endl;
    }
    std::cout << std::endl;
}

void testResetAceleraciones() {
    std::cout << "=== Test: Reset de aceleraciones ===" << std::endl;

    NBodySystem sys(1.0, 0.1);
    sys.addParticle(Particle(1.0, 0.0, 0.0));
    sys.addParticle(Particle(1.0, 1.0, 0.0));

    sys.computeAccelerations();
    sys.zeroAccelerations();

    auto& particles = sys.getParticles();
    double tolerancia = 1e-15;
    bool ok = true;

    for (int i = 0; i < sys.size(); ++i) {
        if (std::abs(particles[i].getAx()) > tolerancia ||
            std::abs(particles[i].getAy()) > tolerancia) {
            std::cout << RED << "  [FAIL] Particula " << i 
                      << " no fue reseteada" << RESET << std::endl;
            ok = false;
        }
    }

    if (ok) {
        std::cout << GREEN << "  [PASS] Aceleraciones reseteadas correctamente" 
                  << RESET << std::endl;
    }
    std::cout << std::endl;
}

void testTresCuerpos() {
    std::cout << "=== Test: Tres cuerpos - accion reaccion ===" << std::endl;

    NBodySystem sys(1.0, 0.1);
    sys.addParticle(Particle(1.0,  0.0,  0.0));
    sys.addParticle(Particle(2.0,  3.0,  0.0));
    sys.addParticle(Particle(1.5,  0.0,  4.0));

    sys.computeAccelerations();

    auto& p = sys.getParticles();
    double tolerancia = 1e-10;
    bool ok = true;

    // Momento lineal total debe conservarse: sum(m_i * a_i) = 0
    double px = p[0].getMass()*p[0].getAx() + 
                p[1].getMass()*p[1].getAx() + 
                p[2].getMass()*p[2].getAx();
    double py = p[0].getMass()*p[0].getAy() + 
                p[1].getMass()*p[1].getAy() + 
                p[2].getMass()*p[2].getAy();

    std::cout << "  Suma m*ax = " << px << " (esperado ~0)" << std::endl;
    std::cout << "  Suma m*ay = " << py << " (esperado ~0)" << std::endl;

    if (std::abs(px) > tolerancia || std::abs(py) > tolerancia) {
        std::cout << RED << "  [FAIL] Suma de fuerzas no es cero" 
                  << RESET << std::endl;
        ok = false;
    }

    if (ok) {
        std::cout << GREEN << "  [PASS] Conservacion de momento verificada" 
                  << RESET << std::endl;
    }
    std::cout << std::endl;
}

void testKickDrift() {
    std::cout << "=== Test: Kick y Drift ===" << std::endl;

    Particle p(1.0, 0.0, 0.0, 0.0, 0.0);
    p.setAcceleration(1.0, 0.0); // aceleracion en x

    double dt = 0.1;
    p.kick(dt);  // vx = 0 + 1*0.1 = 0.1
    p.drift(dt); 

    double tolerancia = 1e-12;
    bool ok = true;

    std::cout << "  vx=" << p.getVx() << " (esperado 0.1)" << std::endl;
    std::cout << "  x="  << p.getX()  << " (esperado 0.01)" << std::endl;

    if (std::abs(p.getVx() - 0.1)  > tolerancia) {
        std::cout << RED << "  [FAIL] kick incorrecto" << RESET << std::endl;
        ok = false;
    }
    if (std::abs(p.getX()  - 0.01) > tolerancia) {
        std::cout << RED << "  [FAIL] drift incorrecto" << RESET << std::endl;
        ok = false;
    }

    if (ok) {
        std::cout << GREEN << "  [PASS] Kick y drift correctos" 
                  << RESET << std::endl;
    }
    std::cout << std::endl;
}

int main() {
    std::cout << "========================================" << std::endl;
    std::cout << "  Tests Particle y NBodySystem"           << std::endl;
    std::cout << "========================================" << std::endl;
    std::cout << std::endl;

    testEjemploEnunciado();
    testResetAceleraciones();
    testTresCuerpos();
    testKickDrift();

    std::cout << "========================================" << std::endl;
    std::cout << "  Tests completados"                      << std::endl;
    std::cout << "========================================" << std::endl;

    return 0;
}