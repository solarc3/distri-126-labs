#ifndef ACCELERATIONS_CUH
#define ACCELERATIONS_CUH

void launchComputeAccelerations(const double* d_x, const double* d_y,
                                const double* d_mass,
                                double* d_ax, double* d_ay,
                                int n, double G, double eps2,
                                int variant, int block_size);

#endif
