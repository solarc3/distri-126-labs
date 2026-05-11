#include "Particle.h"
#include <ostream>

// Constructor por defecto: deja una partícula válida y finita.
Particle::Particle()
    : x(0.0), y(0.0), vx(0.0), vy(0.0), ax(0.0), ay(0.0), mass(0.0), padding{} {}

// Constructor: inicializa los atributos físicos
Particle::Particle(double start_x, double start_y, double start_vx, double start_vy, double m)
    : x(start_x), y(start_y), vx(start_vx), vy(start_vy), ax(0.0), ay(0.0), mass(m), padding{} {}

// Reiniciar la aceleración antes de calcular las nuevas fuerzas
void Particle::resetAcceleration() {
    ax = 0.0;
    ay = 0.0;
}

void Particle::addAcceleration(double dax, double day) {
    ax += dax;
    ay += day;
}

void Particle::kick(double dt) {
    vx += ax * dt;
    vy += ay * dt;
}

void Particle::drift(double dt) {
    x += vx * dt;
    y += vy * dt;
}

void Particle::writeToStream(std::ostream& out) const {
    out << x << ' '
        << y << ' '
        << vx << ' '
        << vy << ' '
        << mass << ' '
        << ax << ' '
        << ay;
}

double Particle::getX() const {
    return x;
}

double Particle::getY() const {
    return y;
}

double Particle::getVx() const {
    return vx;
}

double Particle::getVy() const {
    return vy;
}

double Particle::getMass() const {
    return mass;
}

double Particle::getAx() const {
    return ax;
}

double Particle::getAy() const {
    return ay;
}
