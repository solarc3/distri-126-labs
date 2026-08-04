#ifndef ACCELERATIONS_CUH
#define ACCELERATIONS_CUH

#if __has_include(<cuda_runtime.h>)
#include <cuda_runtime.h>

// Multi-GPU: cada device calcula el slice [i_begin, i_begin+i_count) de
// aceleraciones. d_x/d_y/d_mass deben contener las n particulas completas;
// d_ax/d_ay son buffers LOCALES del device, de tamano i_count.
void launchComputeAccelerations(const double* d_x, const double* d_y,
                                const double* d_mass,
                                double* d_ax, double* d_ay,
                                int n, int i_begin, int i_count,
                                double G, double eps2,
                                int variant, int block_size);

// Overload de compatibilidad: single-GPU, equivalente a i_begin=0, i_count=n.
void launchComputeAccelerations(const double* d_x, const double* d_y,
                                const double* d_mass,
                                double* d_ax, double* d_ay,
                                int n, double G, double eps2,
                                int variant, int block_size);
#else

inline void launchComputeAccelerations(const double*, const double*,
                                       const double*,
                                       double*, double*,
                                       int, int, int,
                                       double, double,
                                       int, int) {}

inline void launchComputeAccelerations(const double*, const double*,
                                       const double*,
                                       double*, double*,
                                       int, double, double,
                                       int, int) {}
#endif

#endif
