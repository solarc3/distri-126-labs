#ifndef ENERGY_CUH
#define ENERGY_CUH

#if __has_include(<cuda_runtime.h>)
#include <cuda_runtime.h>

// Multi-GPU: reduccion PARCIAL sobre el slice [i_begin, i_begin+i_count) de
// particulas i. d_x/d_y/d_mass/d_vx/d_vy deben tener las n particulas
// completas (j recorre todo n en el termino potencial). h_kinetic/h_potential
// reciben solo la contribucion de este device; el caller debe sumar las
// reducciones parciales de todos los devices para el total.
void launchComputeEnergy(const double* d_x, const double* d_y,
                          const double* d_mass,
                          const double* d_vx, const double* d_vy,
                          int n, int i_begin, int i_count,
                          double G, double eps2,
                          double* h_kinetic, double* h_potential,
                          int method);

// Overload de compatibilidad: single-GPU, equivalente a i_begin=0, i_count=n.
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
                                int, int, int,
                                double, double,
                                double*, double*,
                                int) {}

inline void launchComputeEnergy(const double*, const double*,
                                const double*,
                                const double*, const double*,
                                int, double, double,
                                double*, double*,
                                int) {}
#endif

#endif
