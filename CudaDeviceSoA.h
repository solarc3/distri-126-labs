#ifndef CUDA_DEVICE_SOA_H
#define CUDA_DEVICE_SOA_H

#include <cstddef>
#include <vector>
#include <stdexcept>
#include "CudaBuffer.h"


// Representa TODO lo de una sola GPU: buffers de entrada (x,y,mass, tamano
// completo n) y de salida (ax,ay). En el caso single-device, ax/ay tienen el
// mismo tamano que las entradas (i_begin=0, i_count=n). En multi-GPU,
// NBodySimulator mantiene un std::vector<CudaDeviceSoA> (uno por device);
// cada instancia replica x/y/mass completos pero solo alcanza ax/ay para su
// slice [i_begin, i_begin+i_count) -- ver allocateSlice().
//
// Decision de diseno: esta clase NO llama cudaSetDevice por si sola en cada
// operacion (evitar overhead/duplicidad con el fix de CudaBuffer). El
// invariante es que el caller (NBodySimulator) hace cudaSetDevice(device_id)
// antes de invocar allocate/copyHostToDevice/etc. sobre la instancia de ese
// device; los CudaBuffer internos igualmente guardan su propio device_id_
// como red de seguridad para el destructor.
class CudaDeviceSoA {
private:
    size_t size_{0};      // tamano de las entradas (x,y,mass) == n
    size_t capacity_{0};  // capacidad reservada para las entradas
    size_t out_size_{0};      // tamano de las salidas (ax,ay) == i_count
    size_t out_capacity_{0};  // capacidad reservada para las salidas
    size_t i_begin_{0};       // offset del slice de este device dentro de [0,n)
    int device_id_{0};

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

    // Reserva memoria GPU suficiente para 'count' elementos (caso
    // single-device: entradas y salidas del mismo tamano).
    void allocate(size_t count) {
        allocateSlice(count, 0, count);
    }

    // Reserva memoria para el caso multi-GPU: entradas de tamano 'n'
    // (replicadas completas en cada device) y salidas de tamano 'i_count'
    // (solo el slice que le corresponde a este device, arrancando en
    // i_begin dentro del rango global [0,n)).
    void allocateSlice(size_t n, size_t i_begin, size_t i_count) {
        if (n > capacity_) {
            d_x = CudaBuffer<double>(n);
            d_y = CudaBuffer<double>(n);
            d_mass = CudaBuffer<double>(n);
            capacity_ = n;
        }
        if (i_count > out_capacity_) {
            d_ax = CudaBuffer<double>(i_count);
            d_ay = CudaBuffer<double>(i_count);
            out_capacity_ = i_count;
        }
        size_ = n;
        out_size_ = i_count;
        i_begin_ = i_begin;
        is_device_inputs_synced_ = false;
        is_host_outputs_synced_ = false;
    }

    void setDeviceId(int device_id) noexcept { device_id_ = device_id; }
    int deviceId() const noexcept { return device_id_; }
    size_t iBegin() const noexcept { return i_begin_; }
    size_t outSize() const noexcept { return out_size_; }

    void copyHostToDevice(const double* h_x, const double* h_y, const double* h_mass, size_t count) {
        if (count > capacity_ || out_capacity_ < count) {
            allocate(count);
        } else {
            size_ = count;
            out_size_ = count;
            i_begin_ = 0;
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

    // Copia las entradas completas (x,y,mass) de tamano n, util en multi-GPU
    // donde cada device necesita ver todas las particulas.
    void copyFullInputsToDevice(const double* h_x, const double* h_y, const double* h_mass, size_t n) {
        if (n > capacity_) {
            d_x = CudaBuffer<double>(n);
            d_y = CudaBuffer<double>(n);
            d_mass = CudaBuffer<double>(n);
            capacity_ = n;
        }
        size_ = n;
        if (n == 0) {
            is_device_inputs_synced_ = true;
            return;
        }
        if (h_x == nullptr || h_y == nullptr || h_mass == nullptr) {
            throw std::invalid_argument("CudaDeviceSoA::copyFullInputsToDevice: punteros host nulos con n > 0");
        }
        d_x.copyFromHost(h_x, n);
        d_y.copyFromHost(h_y, n);
        d_mass.copyFromHost(h_mass, n);
        is_device_inputs_synced_ = true;
        is_host_outputs_synced_ = false;
    }

    void copyDeviceToHost(double* h_ax, double* h_ay, size_t count) {
        if (count > out_size_) {
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
        if (h_ax.size() < out_size_) h_ax.resize(out_size_);
        if (h_ay.size() < out_size_) h_ay.resize(out_size_);
        copyDeviceToHost(h_ax.data(), h_ay.data(), out_size_);
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
