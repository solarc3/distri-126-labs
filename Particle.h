#ifndef PARTICLE_H
#define PARTICLE_H

#include <iosfwd>

class Particle {
    private:
        double x, y;       // Posición en 2D
        double vx, vy;     // Velocidad
        double ax, ay;     // Aceleración (se acumula en cada paso)
        double mass;       // Masa de la partícula

public:
    // Constructor
    Particle(double start_x, double start_y, double start_vx, double start_vy, double m);

    // Método para limpiar la aceleración en cada nuevo paso de tiempo
    void resetAcceleration();
    void addAcceleration(double dax, double day);
    void kick(double dt);
    void drift(double dt);
    void writeToStream(std::ostream& out) const;

    double getX() const;
    double getY() const;
    double getVx() const;
    double getVy() const;
    double getMass() const;
    double getAx() const;
    double getAy() const;
};

#endif