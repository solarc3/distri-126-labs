#include <iostream>
#include <cassert>
#include <vector>
#include "../CudaDeviceSoA.h"

void testDeviceSoALayoutAllocation() {
    size_t n = 1000;
    CudaDeviceSoA dev_soa(n);

    assert(dev_soa.size() == n);
    assert(dev_soa.capacity() >= n);

    assert(dev_soa.d_x.size() == n);
    assert(dev_soa.d_y.size() == n);
    assert(dev_soa.d_mass.size() == n);
    assert(dev_soa.d_ax.size() == n);
    assert(dev_soa.d_ay.size() == n);

    assert(dev_soa.d_x.get() != nullptr);
    assert(dev_soa.d_y.get() != nullptr);
    assert(dev_soa.d_mass.get() != nullptr);
    assert(dev_soa.d_ax.get() != nullptr);
    assert(dev_soa.d_ay.get() != nullptr);

    std::cout << "[PASS] testDeviceSoALayoutAllocation (Tarea 1)" << std::endl;
}

void testHostDeviceTransferContract() {
    size_t n = 5;
    std::vector<double> h_x = {1.0, 2.0, 3.0, 4.0, 5.0};
    std::vector<double> h_y = {10.0, 20.0, 30.0, 40.0, 50.0};
    std::vector<double> h_mass = {0.5, 1.5, 2.5, 3.5, 4.5};

    CudaDeviceSoA dev_soa;
    dev_soa.copyHostToDevice(h_x, h_y, h_mass);

    assert(dev_soa.size() == n);
    assert(dev_soa.isDeviceInputsSynced());

    std::vector<double> dummy_ax = {0.1, 0.2, 0.3, 0.4, 0.5};
    std::vector<double> dummy_ay = {-0.1, -0.2, -0.3, -0.4, -0.5};
    dev_soa.d_ax.copyFromHost(dummy_ax.data(), n);
    dev_soa.d_ay.copyFromHost(dummy_ay.data(), n);

    std::vector<double> res_ax(n, 0.0);
    std::vector<double> res_ay(n, 0.0);
    dev_soa.copyDeviceToHost(res_ax, res_ay);

    for (size_t i = 0; i < n; ++i) {
        assert(res_ax[i] == dummy_ax[i]);
        assert(res_ay[i] == dummy_ay[i]);
    }

    std::cout << "[PASS] testHostDeviceTransferContract (Tarea 2)" << std::endl;
}

void testSynchronizationAndTransferMinimization() {
    size_t n = 10;
    CudaDeviceSoA dev_soa(n);

    dev_soa.synchronize();

    std::vector<double> h_x(n, 1.0), h_y(n, 2.0), h_mass(n, 3.0);
    dev_soa.copyHostToDevice(h_x, h_y, h_mass);

    assert(dev_soa.isDeviceInputsSynced() == true);
    assert(dev_soa.isHostOutputsSynced() == false);


    dev_soa.markDeviceInputsUpdated();
    assert(dev_soa.isDeviceInputsSynced() == true);

    std::cout << "[PASS] testSynchronizationAndTransferMinimization (Tarea 3)" << std::endl;
}

int main() {
    std::cout << "--- Ejecutando pruebas unitarias de CudaDeviceSoA ---" << std::endl;
    testDeviceSoALayoutAllocation();
    testHostDeviceTransferContract();
    testSynchronizationAndTransferMinimization();
    std::cout << "--- Todas las pruebas de CudaDeviceSoA pasaron exitosamente ---" << std::endl;
    return 0;
}
