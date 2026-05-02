#ifndef INTEGRATOR_H
#define INTEGRATOR_H

#include <vector>
#include "Particle.h"

enum class SyncType {
    ATOMIC = 0,
    CRITICAL = 1,
    NOWAIT = 2,
    NORMAL = 3
};

class Integrator {
public:
    static void integrateEuler(std::vector<Particle>& particles, double dt, SyncType sync_type = SyncType::NORMAL);
};

#endif
