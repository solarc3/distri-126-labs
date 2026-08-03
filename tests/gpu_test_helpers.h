#ifndef GPU_TEST_HELPERS_H
#define GPU_TEST_HELPERS_H

#include <cmath>
#include <algorithm>
#include <vector>
#include <string>
#include "../Particle.h"
#include <gtest/gtest.h>

#ifdef NBODY_ENABLE_CUDA_KERNELS
#include <cuda_runtime.h>

// Los runners de CI (GitHub Actions) compilan y linkean los kernels reales
// pero no tienen GPU fisica: cudaGetDeviceCount() devuelve 0 en vez de un
// error de compilacion. Sin esta guarda, los tests de equivalencia CPU vs
// GPU comparan el resultado real contra basura de un kernel que nunca corrio.
inline bool gpuDeviceAvailable() {
    int deviceCount = 0;
    cudaError_t err = cudaGetDeviceCount(&deviceCount);
    return err == cudaSuccess && deviceCount > 0;
}

#define SKIP_IF_NO_GPU()                                                    \
    do {                                                                    \
        if (!gpuDeviceAvailable()) {                                        \
            GTEST_SKIP() << "No hay GPU CUDA disponible en este runner";    \
        }                                                                   \
    } while (0)
#else
#define SKIP_IF_NO_GPU() do {} while (0)
#endif

constexpr double kGpuRtol = 1e-4;
constexpr double kGpuAtol = 1e-8;

inline bool compareFloat(double a, double b, double rtol = kGpuRtol, double atol = kGpuAtol) {
    double abs_diff = std::fabs(a - b);
    double max_mag = std::max(std::fabs(a), std::fabs(b));
    return abs_diff <= (atol + rtol * max_mag);
}

inline bool compareFloatArray(const std::vector<double>& a, const std::vector<double>& b,
                              double rtol = kGpuRtol, double atol = kGpuAtol) {
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); ++i) {
        if (!compareFloat(a[i], b[i], rtol, atol)) return false;
    }
    return true;
}

inline bool compareAccelerations(const Particle& cpu, const Particle& gpu,
                                 double rtol = kGpuRtol, double atol = kGpuAtol) {
    return compareFloat(cpu.getAx(), gpu.getAx(), rtol, atol) &&
           compareFloat(cpu.getAy(), gpu.getAy(), rtol, atol);
}

inline bool compareParticles(const Particle& cpu, const Particle& gpu,
                             double rtol = kGpuRtol, double atol = kGpuAtol) {
    return compareFloat(cpu.getX(),  gpu.getX(),  rtol, atol) &&
           compareFloat(cpu.getY(),  gpu.getY(),  rtol, atol) &&
           compareFloat(cpu.getVx(), gpu.getVx(), rtol, atol) &&
           compareFloat(cpu.getVy(), gpu.getVy(), rtol, atol) &&
           compareFloat(cpu.getAx(), gpu.getAx(), rtol, atol) &&
           compareFloat(cpu.getAy(), gpu.getAy(), rtol, atol);
}

inline bool compareParticleStates(const std::vector<Particle>& cpu,
                                  const std::vector<Particle>& gpu,
                                  double rtol = kGpuRtol, double atol = kGpuAtol) {
    if (cpu.size() != gpu.size()) return false;
    for (size_t i = 0; i < cpu.size(); ++i) {
        if (!compareParticles(cpu[i], gpu[i], rtol, atol)) return false;
    }
    return true;
}

inline std::string mismatchDetail(const std::vector<Particle>& cpu,
                                  const std::vector<Particle>& gpu,
                                  double rtol = kGpuRtol, double atol = kGpuAtol) {
    if (cpu.size() != gpu.size()) {
        return "size mismatch cpu=" + std::to_string(cpu.size()) +
               " gpu=" + std::to_string(gpu.size());
    }

    for (size_t i = 0; i < cpu.size(); ++i) {
        if (!compareFloat(cpu[i].getX(), gpu[i].getX(), rtol, atol))
            return "x[" + std::to_string(i) + "] cpu=" + std::to_string(cpu[i].getX()) +
                   " gpu=" + std::to_string(gpu[i].getX());
        if (!compareFloat(cpu[i].getY(), gpu[i].getY(), rtol, atol))
            return "y[" + std::to_string(i) + "] cpu=" + std::to_string(cpu[i].getY()) +
                   " gpu=" + std::to_string(gpu[i].getY());
        if (!compareFloat(cpu[i].getVx(), gpu[i].getVx(), rtol, atol))
            return "vx[" + std::to_string(i) + "] cpu=" + std::to_string(cpu[i].getVx()) +
                   " gpu=" + std::to_string(gpu[i].getVx());
        if (!compareFloat(cpu[i].getVy(), gpu[i].getVy(), rtol, atol))
            return "vy[" + std::to_string(i) + "] cpu=" + std::to_string(cpu[i].getVy()) +
                   " gpu=" + std::to_string(gpu[i].getVy());
        if (!compareFloat(cpu[i].getAx(), gpu[i].getAx(), rtol, atol))
            return "ax[" + std::to_string(i) + "] cpu=" + std::to_string(cpu[i].getAx()) +
                   " gpu=" + std::to_string(gpu[i].getAx());
        if (!compareFloat(cpu[i].getAy(), gpu[i].getAy(), rtol, atol))
            return "ay[" + std::to_string(i) + "] cpu=" + std::to_string(cpu[i].getAy()) +
                   " gpu=" + std::to_string(gpu[i].getAy());
    }
    return "";
}

#endif
