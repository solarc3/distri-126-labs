#ifndef PARTICLE_H
#define PARTICLE_H

class Particle {
public:
    double x, y;       // Posición en 2D
    double vx, vy;     // Velocidad
    double ax, ay;     // Aceleración (se acumula en cada paso)
    double mass;       // Masa de la partícula

    // Constructor
    Particle(double start_x, double start_y, double start_vx, double start_vy, double m);

    // Método para limpiar la aceleración en cada nuevo paso de tiempo
    void resetAcceleration();
};

#endif