#ifndef GPU_DEVICE_SPLIT_H
#define GPU_DEVICE_SPLIT_H

#include <vector>

// Descomposicion por particula de salida: reparte n particulas entre
// num_devices GPUs de forma lo mas uniforme posible. Es una funcion pura
// (sin dependencias de CUDA) para poder testearla sin GPU real.
struct GpuDeviceRange {
    int i_begin{0};
    int i_count{0};
};

// Reparte [0, n) en como maximo num_devices slices contiguos.
// - Si n <= 0 o num_devices <= 0, retorna vacio (nada que repartir).
// - Si num_devices > n, se limita a n devices (uno por particula) para
//   evitar devices con i_count == 0.
// - El resto de la division (n % num_devices) se reparte de a uno entre los
//   primeros 'resto' devices, asi el tamano de cada slice difiere como
//   maximo en 1 particula entre devices.
inline std::vector<GpuDeviceRange> splitParticleRange(int n, int num_devices) {
    std::vector<GpuDeviceRange> ranges;
    if (n <= 0 || num_devices <= 0) {
        return ranges;
    }
    if (num_devices > n) {
        num_devices = n;
    }

    const int base = n / num_devices;
    const int remainder = n % num_devices;

    ranges.reserve(static_cast<std::size_t>(num_devices));
    int begin = 0;
    for (int d = 0; d < num_devices; ++d) {
        const int count = base + (d < remainder ? 1 : 0);
        ranges.push_back(GpuDeviceRange{begin, count});
        begin += count;
    }
    return ranges;
}

#endif
