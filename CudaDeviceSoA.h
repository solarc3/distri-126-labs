#ifndef CUDA_DEVICE_SOA_H
#define CUDA_DEVICE_SOA_H

#include <cstddef>
#include <vector>
#include <stdexcept>
#include "CudaBuffer.h"


class CudaDeviceSoA {
private:
    size_t size_{0};
    size_t capacity_{0};

    bool is_device_inputs_synced_{false};
    bool is_host_outputs_synced_{false};

public:

    CudaBuffer<double> d_x;
    CudaBuffer<double> d_y;
    CudaBuffer<double> d_mass;
    CudaBuffer<double> d_ax;
    CudaBuffer<double> d_ay;

    CudaDeviceSoA() = default;

    explicit CudaDeviceSoA(size_t count) {
        allocate(count);
    }

    // Reserva memoria GPU suficiente para 'count' elementos
    void allocate(size_t count) {
        if (count > capacity_) {
            d_x = CudaBuffer<double>(count);
            d_y = CudaBuffer<double>(count);
            d_mass = CudaBuffer<double>(count);
            d_ax = CudaBuffer<double>(count);
            d_ay = CudaBuffer<double>(count);
            capacity_ = count;
        }
        size_ = count;
        is_device_inputs_synced_ = false;
        is_host_outputs_synced_ = false;
    }

    void copyHostToDevice(const double* h_x, const double* h_y, const double* h_mass, size_t count) {
        if (count > capacity_) {
            allocate(count);
        } else {
            size_ = count;
            is_device_inputs_synced_ = false;
            is_host_outputs_synced_ = false;
        }

        if (count == 0) {
            return;
        }
        if (h_x == nullptr || h_y == nullptr || h_mass == nullptr) {
            throw std::invalid_argument("CudaDeviceSoA::copyHostToDevice: punteros host nulos con count > 0");
        }

        d_x.copyFromHost(h_x, count);
        d_y.copyFromHost(h_y, count);
        d_mass.copyFromHost(h_mass, count);
        is_device_inputs_synced_ = true;
        is_host_outputs_synced_ = false;
    }

    void copyHostToDevice(const std::vector<double>& h_x,
                          const std::vector<double>& h_y,
                          const std::vector<double>& h_mass) {
        if (h_x.size() != h_y.size() || h_x.size() != h_mass.size()) {
            throw std::invalid_argument("CudaDeviceSoA::copyHostToDevice: Las dimensiones de los vectores no coinciden");
        }
        copyHostToDevice(h_x.data(), h_y.data(), h_mass.data(), h_x.size());
    }

    void copyDeviceToHost(double* h_ax, double* h_ay, size_t count) {
        if (count > size_) {
            throw std::out_of_range("CudaDeviceSoA::copyDeviceToHost: la cantidad excede el tamaño asignado");
        }
        if (count == 0) {
            is_host_outputs_synced_ = true;
            return;
        }
        if (h_ax == nullptr || h_ay == nullptr) {
            throw std::invalid_argument("CudaDeviceSoA::copyDeviceToHost: punteros host nulos con count > 0");
        }

        d_ax.copyToHost(h_ax, count);
        d_ay.copyToHost(h_ay, count);
        is_host_outputs_synced_ = true;
    }

    void copyDeviceToHost(std::vector<double>& h_ax, std::vector<double>& h_ay) {
        if (h_ax.size() < size_) h_ax.resize(size_);
        if (h_ay.size() < size_) h_ay.resize(size_);
        copyDeviceToHost(h_ax.data(), h_ay.data(), size_);
    }

    void synchronize() const {
        CUDA_CHECK(cudaDeviceSynchronize());
    }

    void markDeviceInputsUpdated() noexcept {
        is_device_inputs_synced_ = true;
        is_host_outputs_synced_ = false;
    }


    bool isDeviceInputsSynced() const noexcept {
        return is_device_inputs_synced_;
    }

    bool isHostOutputsSynced() const noexcept {
        return is_host_outputs_synced_;
    }

    void markHostOutputsSynced() noexcept {
        is_host_outputs_synced_ = true;
    }

    size_t size() const noexcept { return size_; }
    size_t capacity() const noexcept { return capacity_; }
};

#endif 
