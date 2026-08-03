#include "accelerations.cuh"
#include <cassert>
#include <cuda_runtime.h>
#include <stdexcept>
#include <string>

static constexpr int kDefaultBlockSize = 256;

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


__global__ void computeAccelerationsKernelShared(const double* __restrict__ d_x,
                                                 const double* __restrict__ d_y,
                                                 const double* __restrict__ d_mass,
                                                 double* __restrict__ d_ax,
                                                 double* __restrict__ d_ay,
                                                 int n, double G, double eps2)
{
    //s_x | s_y | s_mass cada blockDim.x doubles
    extern __shared__ double smem[];
    double* s_x    = smem;
    double* s_y    = smem + blockDim.x;
    double* s_mass = smem + 2 * blockDim.x;

    const int bdim = static_cast<int>(blockDim.x);
    const int tid  = static_cast<int>(threadIdx.x);
    const int i    = blockIdx.x * bdim + tid;
    const bool active = (i < n);

    const double xi = active ? d_x[i] : 0.0;
    const double yi = active ? d_y[i] : 0.0;
    double ax = 0.0, ay = 0.0;

    const int numTiles = (n + bdim - 1) / bdim;

    for (int t = 0; t < numTiles; ++t) {
        const int j = t * bdim + tid;
        const bool jValid = (j < n);
        s_x[tid]    = jValid ? d_x[j]    : 0.0;
        s_y[tid]    = jValid ? d_y[j]    : 0.0;
        s_mass[tid] = jValid ? d_mass[j] : 0.0;

        __syncthreads();

        const int kmax = min(bdim, n - t * bdim);

        for (int k = 0; k < kmax; ++k) {
            const int jg = t * bdim + k;

            if (eps2 == 0.0 && jg == i) continue;

            const double dx = s_x[k] - xi;
            const double dy = s_y[k] - yi;
            const double r2 = dx * dx + dy * dy + eps2;
            const double inv_r  = rsqrt(r2);
            const double inv_r3 = inv_r * inv_r * inv_r;
            const double s = s_mass[k] * inv_r3;
            ax += s * dx;
            ay += s * dy;
        }

        __syncthreads();//WAR podria existir
    }

    if (active) {
        d_ax[i] = G * ax;
        d_ay[i] = G * ay;
    }
}

// no hace sync pq eso lo ve el caller
void launchComputeAccelerations(const double* d_x, const double* d_y,
                                const double* d_mass,
                                double* d_ax, double* d_ay,
                                int n, double G, double eps2,
                                int variant, int block_size)
{
    if (n == 0) return;
    assert(eps2 >= 0.0);

    if (block_size <= 0) block_size = kDefaultBlockSize;
    const int grid_size = (n + block_size - 1) / block_size;//upper divide

    switch (variant) {
        case 0:
            computeAccelerationsKernel<<<grid_size, block_size>>>(
                d_x, d_y, d_mass, d_ax, d_ay, n, G, eps2);
            break;

        case 1: {
            const size_t smem_bytes =
                3 * static_cast<size_t>(block_size) * sizeof(double);
            computeAccelerationsKernelShared<<<grid_size, block_size, smem_bytes>>>(
                d_x, d_y, d_mass, d_ax, d_ay, n, G, eps2);
            break;
        }

        default:
            throw std::runtime_error(
                "launchComputeAccelerations: variante desconocida "
                "(esperado 0 o 1), recibido " + std::to_string(variant));
    }
    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess) {
        throw std::runtime_error(
            std::string("launchComputeAccelerations: error al lanzar kernel - ")
            + cudaGetErrorString(err));
    }
}
