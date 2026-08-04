#ifndef CUDA_BUFFER_H
#define CUDA_BUFFER_H

#include <cstddef>
#include <cstring>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <utility>

#if __has_include(<cuda_runtime.h>)
#include <cuda_runtime.h>
#else
typedef int cudaError_t;
#define cudaSuccess 0
#define cudaMemcpyHostToDevice 1
#define cudaMemcpyDeviceToHost 2
#define cudaMemcpyDeviceToDevice 3

inline const char* cudaGetErrorString(cudaError_t err) {
    return (err == cudaSuccess) ? "cudaSuccess" : "cudaErrorUnknown";
}

inline cudaError_t cudaMalloc(void** ptr, size_t size) {
    if (size == 0) {
        *ptr = nullptr;
        return cudaSuccess;
    }
    *ptr = std::malloc(size);
    return (*ptr != nullptr) ? cudaSuccess : 1;
}

inline cudaError_t cudaFree(void* ptr) {
    if (ptr) std::free(ptr);
    return cudaSuccess;
}

inline cudaError_t cudaMemcpy(void* dst, const void* src, size_t count, int kind) {
    (void)kind;
    if (count > 0 && dst && src) {
        std::memcpy(dst, src, count);
    }
    return cudaSuccess;
}

inline cudaError_t cudaDeviceSynchronize() {
    return cudaSuccess;
}

inline cudaError_t cudaGetDevice(int* device) {
    if (device) *device = 0;
    return cudaSuccess;
}

inline cudaError_t cudaSetDevice(int) {
    return cudaSuccess;
}

inline cudaError_t cudaGetDeviceCount(int* count) {
    // Sin CUDA real no hay devices; el caller (NBodySimulator) debe caer a
    // la ruta CPU cuando esto devuelve 0.
    if (count) *count = 0;
    return cudaSuccess;
}
#endif

#ifndef CUDA_CHECK
#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = (call); \
        if (err != cudaSuccess) { \
            throw std::runtime_error(std::string("CUDA Error: ") + \
                                     cudaGetErrorString(err) + \
                                     " at " + __FILE__ + ":" + \
                                     std::to_string(__LINE__)); \
        } \
    } while (0)
#endif

template <typename T>
class CudaBuffer {
private:
    T* d_ptr_{nullptr};
    size_t size_{0};

    void freeGPU() noexcept {
        if (d_ptr_ != nullptr) {
            cudaFree(d_ptr_);
            d_ptr_ = nullptr;
            size_ = 0;
        }
    }

public:
    CudaBuffer() noexcept = default;

    explicit CudaBuffer(size_t count) : size_(count) {
        if (size_ > 0) {
            CUDA_CHECK(cudaMalloc(reinterpret_cast<void**>(&d_ptr_), size_ * sizeof(T)));
        }
    }

    ~CudaBuffer() noexcept {
        freeGPU();
    }

    CudaBuffer(const CudaBuffer&) = delete;
    CudaBuffer& operator=(const CudaBuffer&) = delete;

    CudaBuffer(CudaBuffer&& other) noexcept
        : d_ptr_(other.d_ptr_), size_(other.size_) {
        other.d_ptr_ = nullptr;
        other.size_ = 0;
    }

    CudaBuffer& operator=(CudaBuffer&& other) noexcept {
        if (this != &other) {
            freeGPU();
            d_ptr_ = other.d_ptr_;
            size_ = other.size_;
            other.d_ptr_ = nullptr;
            other.size_ = 0;
        }
        return *this;
    }

    void copyFromHost(const T* host_ptr, size_t count) {
        if (count > size_) {
            throw std::out_of_range("CudaBuffer::copyFromHost: la cantidad de elementos excede el tamaño del buffer");
        }
        if (count == 0) {
            return;
        }
        if (host_ptr == nullptr) {
            throw std::invalid_argument("CudaBuffer::copyFromHost: host_ptr es null con count > 0");
        }
        if (d_ptr_ == nullptr) {
            throw std::logic_error("CudaBuffer::copyFromHost: buffer no asignado con count > 0");
        }
        CUDA_CHECK(cudaMemcpy(d_ptr_, host_ptr, count * sizeof(T), cudaMemcpyHostToDevice));
    }

    void copyFromHost(const T* host_ptr) {
        copyFromHost(host_ptr, size_);
    }

    void copyToHost(T* host_ptr, size_t count) const {
        if (count > size_) {
            throw std::out_of_range("CudaBuffer::copyToHost: la cantidad de elementos excede el tamaño del buffer");
        }
        if (count > 0 && host_ptr != nullptr && d_ptr_ != nullptr) {
            CUDA_CHECK(cudaMemcpy(host_ptr, d_ptr_, count * sizeof(T), cudaMemcpyDeviceToHost));
        }
    }

    void copyToHost(T* host_ptr) const {
        copyToHost(host_ptr, size_);
    }

    T* get() noexcept { return d_ptr_; }
    const T* get() const noexcept { return d_ptr_; }

    T* data() noexcept { return d_ptr_; }
    const T* data() const noexcept { return d_ptr_; }

    size_t size() const noexcept { return size_; }
    size_t bytes() const noexcept { return size_ * sizeof(T); }

    explicit operator bool() const noexcept { return d_ptr_ != nullptr; }
};

#endif 
