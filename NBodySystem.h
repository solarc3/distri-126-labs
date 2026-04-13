#ifndef NBODYSYSTEM_H
#define NBODYSYSTEM_H
#include <vector>
#include "Particle.h"
#include <string>
class NBodySystem {
private:
    std::vector<Particle> particles;
    double G;
    double epsilon;

public:
    NBodySystem(double G_, double epsilon_);

    void addParticle(const Particle& p);

    void zeroAccelerations();        
    void computeAccelerations();

    std::vector<Particle>& getParticles();
    int size() const;
    double getG() const;
    double getEpsilon() const;
    
};

#endif