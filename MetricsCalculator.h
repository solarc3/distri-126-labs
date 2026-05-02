#ifndef METRICS_CALCULATOR_H
#define METRICS_CALCULATOR_H

#include <vector>
#include "Particle.h" // Asume que aquí defines tu partícula

class MetricsCalculator {
public:
    // Calcula el momento lineal total (Px, Py)
    static std::pair<double, double> calculateTotalMomentum(const std::vector<Particle>& particles);

    // Calcula la posición del centro de masas (CMx, CMy)
    static std::pair<double, double> calculateCenterOfMass(const std::vector<Particle>& particles);

    // Calcula el radio RMS respecto al centro de masas
    static double calculateRMSRadius(const std::vector<Particle>& particles);

    // Calcula la distancia mínima entre cualquier par de partículas
    static double calculateMinDistance(const std::vector<Particle>& particles);
};

#endif