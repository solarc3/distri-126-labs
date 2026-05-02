#ifndef NBODYSIMULATOR_H
#define NBODYSIMULATOR_H

#include <vector>
#include "Particle.h"

class NBodySimulator {
private:
    std::vector<Particle> particles;
    double G;       // Constante gravitacional
    double epsilon; // Factor de suavizado para evitar singularidades (e)

public:
    // Constructor
    NBodySimulator(double g_const, double eps);

    // Agrega una partícula al sistema
    void addParticle(const Particle& p);

    // Calcula las fuerzas/aceleraciones (Aquí meteremos OpenMP en la Fase 2)
    void computeAccelerations(); 

    // Actualiza posiciones y velocidades usando el integrador de Euler
    void integrate(double dt); 

    // Actualiza posiciones y velocidades usando el integrador de Euler (con pruebas de sincronizacion)
    void integrateEuler(double dt, int sync_type);

    // Obtener número de partículas
    int getNumParticles() const;
    
    // (Opcional por ahora) Obtener referencia a las partículas para imprimirlas
    const std::vector<Particle>& getParticles() const; 
    // Calcula la energía cinética y potencial del sistema
    void calculateEnergy(double& kinetic, double& potential);
};

#endif