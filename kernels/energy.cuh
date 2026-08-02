#ifndef ENERGY_CUH
#define ENERGY_CUH

#if __has_include(<cuda_runtime.h>)
#include <cuda_runtime.h>

void launchComputeEnergy(const double* d_x, const double* d_y,
                          const double* d_mass,
                          const double* d_vx, const double* d_vy,
                          int n, double G, double eps2,
                          double* h_kinetic, double* h_potential,
                          int method);
#else

inline void launchComputeEnergy(const double*, const double*,
                                const double*,
                                const double*, const double*,
                                int, double, double,
                                double*, double*,
                                int) {}
#endif

#endif
