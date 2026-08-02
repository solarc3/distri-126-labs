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
    for (int j = 0; j < n; ++j) {
        if (eps2 == 0.0 && j == i) continue;
        const double dx = d_x[j] - xi;
        const double dy = d_y[j] - yi;
        const double r2 = dx * dx + dy * dy + eps2;
        const double inv_r  = rsqrt(r2);
        const double inv_r3 = inv_r * inv_r * inv_r;
        const double s = d_mass[j] * inv_r3;
        ax += s * dx;
        ay += s * dy;
    }

    d_ax[i] = G * ax;
    d_ay[i] = G * ay;
}

static constexpr int kDefaultBlockSize = 256;

void launchComputeAccelerations(const double* d_x, const double* d_y,
                                const double* d_mass,
                                double* d_ax, double* d_ay,
                                int n, double G, double eps2,
                                int variant, int block_size)
{
    if (n == 0) return;
    assert(eps2 >= 0.0);
    (void)variant;

    if (block_size <= 0) block_size = kDefaultBlockSize;
    const int grid_size = (n + block_size - 1) / block_size;

    computeAccelerationsKernel<<<grid_size, block_size>>>(
        d_x, d_y, d_mass, d_ax, d_ay, n, G, eps2);

    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess) {
        throw std::runtime_error(
            std::string("launchComputeAccelerations: error al lanzar kernel - ")
            + cudaGetErrorString(err));
    }
}
