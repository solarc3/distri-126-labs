#include <iostream>
#include <cassert>
#include <vector>
#include <type_traits>
#include "../CudaBuffer.h"


static_assert(!std::is_copy_constructible_v<CudaBuffer<double>>, "CudaBuffer no debe tener constructor de copia");
static_assert(!std::is_copy_assignable_v<CudaBuffer<double>>, "CudaBuffer no debe ser asignable por copia");
static_assert(std::is_move_constructible_v<CudaBuffer<double>>, "CudaBuffer debe ser construible por movimiento");
static_assert(std::is_move_assignable_v<CudaBuffer<double>>, "CudaBuffer debe ser asignable por movimiento");

void testDefaultConstructor() {
    CudaBuffer<float> buf;
    assert(buf.get() == nullptr);
    assert(buf.size() == 0);
    assert(buf.bytes() == 0);
    assert(!buf);
    std::cout << "[PASS] testDefaultConstructor" << std::endl;
}

void testAllocationAndAccessors() {
    size_t n = 100;
    CudaBuffer<double> buf(n);
    assert(buf.get() != nullptr);
    assert(buf.size() == n);
    assert(buf.bytes() == n * sizeof(double));
    assert(static_cast<bool>(buf) == true);
    std::cout << "[PASS] testAllocationAndAccessors" << std::endl;
}

void testMoveConstructor() {
    size_t n = 50;
    CudaBuffer<int> buf1(n);
    int* ptr_original = buf1.get();

    CudaBuffer<int> buf2(std::move(buf1));

    assert(buf2.get() == ptr_original);
    assert(buf2.size() == n);
    assert(buf1.get() == nullptr);
    assert(buf1.size() == 0);
    std::cout << "[PASS] testMoveConstructor" << std::endl;
}

void testMoveAssignment() {
    size_t n1 = 30;
    size_t n2 = 80;
    CudaBuffer<float> buf1(n1);
    CudaBuffer<float> buf2(n2);

    float* ptr1 = buf1.get();

    buf2 = std::move(buf1);

    assert(buf2.get() == ptr1);
    assert(buf2.size() == n1);
    assert(buf1.get() == nullptr);
    assert(buf1.size() == 0);
    std::cout << "[PASS] testMoveAssignment" << std::endl;
}

void testDataTransfer() {
    size_t n = 10;
    std::vector<double> host_src = {1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0};
    std::vector<double> host_dst(n, 0.0);

    CudaBuffer<double> dev_buf(n);
    dev_buf.copyFromHost(host_src.data());
    dev_buf.copyToHost(host_dst.data());

    for (size_t i = 0; i < n; ++i) {
        assert(host_dst[i] == host_src[i]);
    }
    std::cout << "[PASS] testDataTransfer" << std::endl;
}

int main() {
    std::cout << "--- Ejecutando pruebas unitarias de CudaBuffer ---" << std::endl;
    testDefaultConstructor();
    testAllocationAndAccessors();
    testMoveConstructor();
    testMoveAssignment();
    testDataTransfer();
    std::cout << "--- Todas las pruebas de CudaBuffer pasaron exitosamente ---" << std::endl;
    return 0;
}
