#include "energy.cuh"
#include <cassert>
#include <cuda_runtime.h>
#include <stdexcept>
#include <string>

static constexpr int kBlockSize = 256;

// ---------------------------------------------------------------------------
// Kernel de energia cinetica con reduccion en shared memory
// K = 1/2 * sum_i m_i * ||v_i||^2
// ---------------------------------------------------------------------------
__global__ void computeKineticEnergyKernel(const double* d_vx,
                                           const double* d_vy,
                                           const double* d_mass,
                                           int n,
                                           double* d_result)
{
    __shared__ double sdata[kBlockSize];
    const int i = blockIdx.x * kBlockSize + threadIdx.x;
    double val = 0.0;
    if (i < n) {
        val = 0.5 * d_mass[i] * (d_vx[i] * d_vx[i] + d_vy[i] * d_vy[i]);
    }

    sdata[threadIdx.x] = val;
    __syncthreads();

    for (int s = kBlockSize / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) {
            sdata[threadIdx.x] += sdata[threadIdx.x + s];
        }
        __syncthreads();
    }

    if (threadIdx.x == 0) {
        atomicAdd(d_result, sdata[0]);
    }
}

// ---------------------------------------------------------------------------
// Kernel de energia potencial con reduccion en shared memory
// U = -G * sum_i sum_{j > i} m_i * m_j / sqrt(r_ij^2 + eps2)
// ---------------------------------------------------------------------------
__global__ void computePotentialEnergyKernel(const double* d_x,
                                             const double* d_y,
                                             const double* d_mass,
                                             int n,
                                             double G,
                                             double eps2,
                                             double* d_result)
{
    __shared__ double sdata[kBlockSize];
    const int i = blockIdx.x * kBlockSize + threadIdx.x;
    double val = 0.0;

    if (i < n) {
        const double xi = d_x[i];
        const double yi = d_y[i];
        const double mi = d_mass[i];
        const double g = G;
        for (int j = i + 1; j < n; ++j) {
            const double dx = d_x[j] - xi;
            const double dy = d_y[j] - yi;
            const double dist = sqrt(dx * dx + dy * dy + eps2);
            val -= g * mi * d_mass[j] / dist;
        }
    }

    sdata[threadIdx.x] = val;
    __syncthreads();

    for (int s = kBlockSize / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) {
            sdata[threadIdx.x] += sdata[threadIdx.x + s];
        }
        __syncthreads();
    }

    if (threadIdx.x == 0) {
        atomicAdd(d_result, sdata[0]);
    }
}

// ---------------------------------------------------------------------------
// Launcher: asigna buffer de resultado en device, lanza kernels,
// sincroniza y copia de vuelta al host.
// ---------------------------------------------------------------------------
void launchComputeEnergy(const double* d_x, const double* d_y,
                          const double* d_mass,
                          const double* d_vx, const double* d_vy,
                          int n, double G, double eps2,
                          double* h_kinetic, double* h_potential,
                          int method)
{
    if (n == 0) {
        *h_kinetic = 0.0;
        *h_potential = 0.0;
        return;
    }
    (void)method;

    const int grid = (n + kBlockSize - 1) / kBlockSize;

    double* d_K = nullptr;
    double* d_U = nullptr;
    cudaMalloc(&d_K, sizeof(double));
    cudaMalloc(&d_U, sizeof(double));
    cudaMemset(d_K, 0, sizeof(double));
    cudaMemset(d_U, 0, sizeof(double));

    computeKineticEnergyKernel<<<grid, kBlockSize>>>(d_vx, d_vy, d_mass, n, d_K);
    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess) {
        cudaFree(d_K); cudaFree(d_U);
        throw std::runtime_error(
            std::string("launchComputeEnergy: error kinetic kernel - ")
            + cudaGetErrorString(err));
    }

    computePotentialEnergyKernel<<<grid, kBlockSize>>>(
        d_x, d_y, d_mass, n, G, eps2, d_U);
    err = cudaGetLastError();
    if (err != cudaSuccess) {
        cudaFree(d_K); cudaFree(d_U);
        throw std::runtime_error(
            std::string("launchComputeEnergy: error potential kernel - ")
            + cudaGetErrorString(err));
    }

    cudaDeviceSynchronize();

    cudaMemcpy(h_kinetic, d_K, sizeof(double), cudaMemcpyDeviceToHost);
    cudaMemcpy(h_potential, d_U, sizeof(double), cudaMemcpyDeviceToHost);

    cudaFree(d_K);
    cudaFree(d_U);
}
