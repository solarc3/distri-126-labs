#include "accelerations.cuh"
#include <cassert>
#include <cuda_runtime.h>
#include <stdexcept>
#include <string>

__global__ void computeAccelerationsKernel(const double* __restrict__ d_x,
                                           const double* __restrict__ d_y,
                                           const double* __restrict__ d_mass,
                                           double* __restrict__ d_ax,
                                           double* __restrict__ d_ay,
                                           int n, double G, double eps2)
{
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    const double xi = d_x[i];
    const double yi = d_y[i];
    double ax = 0.0, ay = 0.0;
    for (int j = 0; j < n; ++j) {//TODO: hay que verificar con Nsight compute el memory o compute bound para ver si vale la pena hacer loop unrolling o similares
        //verificar tbm -Xptxas -v
        // TODO: benchark con #pragma unroll 4
        const double dx = d_x[j] - xi;
        const double dy = d_y[j] - yi;
        const double r2 = dx * dx + dy * dy + eps2;
        const double inv_r  = rsqrt(r2);// clang cuda math, revisar que mas se podria optimizar
        const double inv_r3 = inv_r * inv_r * inv_r;
        const double s = d_mass[j] * inv_r3;
        ax += s * dx;
        ay += s * dy;
    }

    d_ax[i] = G * ax;
    d_ay[i] = G * ay;
}

//launcher va aca dps
//assert(eps2 > 0.0)
// variant==0
