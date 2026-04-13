#include "Particle.h"


Particle::Particle(double m, double x0, double y0, double vx0, double vy0)
    : mass(m), x(x0), y(y0), vx(vx0), vy(vy0), ax(0.0), ay(0.0) {}

void Particle::setAcceleration(double ax_, double ay_) {
    ax = ax_;
    ay = ay_;
}

void Particle::addAcceleration(double dax, double day) {
    ax += dax;
    ay += day;
}

void Particle::resetAcceleration() {
    ax = 0.0;
    ay = 0.0;
}

void Particle::kick(double dt) {
    vx += ax * dt;
    vy += ay * dt;
}

void Particle::drift(double dt) {
    x += vx * dt;
    y += vy * dt;
}

double Particle::getMass() const {
    return mass;
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

double Particle::getAx() const {
    return ax;
}

double Particle::getAy() const {
    return ay;
}

