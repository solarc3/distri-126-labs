#include "Particle.h"

// Constructor: inicializa los atributos físicos
Particle::Particle(double start_x, double start_y, double start_vx, double start_vy, double m)
    : x(start_x), y(start_y), vx(start_vx), vy(start_vy), ax(0.0), ay(0.0), mass(m) {}

// Reiniciar la aceleración antes de calcular las nuevas fuerzas
void Particle::resetAcceleration() {
    ax = 0.0;
    ay = 0.0;
}