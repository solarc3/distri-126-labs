#ifndef VISUALIZER_H
#define VISUALIZER_H

#include <string>

class NBodySimulator;

class Visualizer {
public:
    static bool exportState(const NBodySimulator& sim, const std::string& filePath);
};

#endif
