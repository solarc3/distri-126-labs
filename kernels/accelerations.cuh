#ifndef ACCELERATIONS_CUH
#define ACCELERATIONS_CUH

#if defined(NBODY_ENABLE_CUDA_KERNELS)
#include <cuda_runtime.h>

void launchComputeAccelerations(const double* d_x, const double* d_y,
                                const double* d_mass,
                                double* d_ax, double* d_ay,
                                int n, double G, double eps2,
                                int variant, int block_size);
#else

inline void launchComputeAccelerations(const double*, const double*,
                                       const double*,
                                       double*, double*,
                                       int, double, double,
                                       int, int) {}
#endif

#endif
