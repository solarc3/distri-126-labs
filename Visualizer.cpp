#include "Visualizer.h"
#include "NBodySimulator.h"
#include <fstream>

bool Visualizer::exportState(const NBodySimulator& sim, const std::string& filePath) {
    std::ofstream out(filePath);
    if (!out.is_open()) {
        return false;
    }

    const auto& particles = sim.getParticles();
    for (const auto& p : particles) {
        p.writeToStream(out);
        out << '\n';
    }

    return out.good();
}
