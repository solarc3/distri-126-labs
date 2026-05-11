#ifndef ALIGNED_ALLOCATOR_H
#define ALIGNED_ALLOCATOR_H

#include <cstddef>
#include <limits>
#include <new>
#include <type_traits>

// Minimal C++17 allocator for cache-line aligned vectors.
// std::vector<T> only guarantees alignof(T); for double that is usually 8 bytes.
// These buffers are used in SIMD kernels, so 64-byte alignment lets AVX-512 loads
// start on cache-line boundaries and makes OpenMP `aligned(...:64)` clauses true.
template <typename T, std::size_t Alignment>
class AlignedAllocator {
    static_assert(Alignment >= alignof(T), "Alignment must satisfy alignof(T)");
    static_assert((Alignment & (Alignment - 1)) == 0, "Alignment must be a power of two");

public:
    using value_type = T;
    using pointer = T*;
    using const_pointer = const T*;
    using reference = T&;
    using const_reference = const T&;
    using size_type = std::size_t;
    using difference_type = std::ptrdiff_t;

    template <typename U>
    struct rebind {
        using other = AlignedAllocator<U, Alignment>;
    };

    AlignedAllocator() noexcept = default;

    template <typename U>
    AlignedAllocator(const AlignedAllocator<U, Alignment>&) noexcept {}

    [[nodiscard]] T* allocate(std::size_t n) {
        if (n > max_size()) {
            throw std::bad_array_new_length();
        }
        if (n == 0) {
            return nullptr;
        }
        void* ptr = ::operator new(n * sizeof(T), std::align_val_t(Alignment));
        return static_cast<T*>(ptr);
    }

    void deallocate(T* ptr, std::size_t) noexcept {
        ::operator delete(ptr, std::align_val_t(Alignment));
    }

    static constexpr std::size_t max_size() noexcept {
        return std::numeric_limits<std::size_t>::max() / sizeof(T);
    }
};

template <typename T, typename U, std::size_t Alignment>
constexpr bool operator==(const AlignedAllocator<T, Alignment>&,
                          const AlignedAllocator<U, Alignment>&) noexcept {
    return true;
}

template <typename T, typename U, std::size_t Alignment>
constexpr bool operator!=(const AlignedAllocator<T, Alignment>&,
                          const AlignedAllocator<U, Alignment>&) noexcept {
    return false;
}

#endif
