#include <gtest/gtest.h>
#include <algorithm>
#include <numeric>
#include "../GpuDeviceSplit.h"

// ---------------------------------------------------------------------------
// splitParticleRange: descomposicion por particula de salida entre devices.
// Funcion pura (sin CUDA), testeable sin GPU real.
// ---------------------------------------------------------------------------

TEST(GpuDeviceSplit, ZeroParticlesReturnsEmpty) {
    auto ranges = splitParticleRange(0, 4);
    EXPECT_TRUE(ranges.empty());
}

TEST(GpuDeviceSplit, ZeroOrNegativeDevicesReturnsEmpty) {
    EXPECT_TRUE(splitParticleRange(100, 0).empty());
    EXPECT_TRUE(splitParticleRange(100, -1).empty());
}

TEST(GpuDeviceSplit, NegativeParticlesReturnsEmpty) {
    EXPECT_TRUE(splitParticleRange(-5, 2).empty());
}

TEST(GpuDeviceSplit, SingleDeviceGetsEverything) {
    auto ranges = splitParticleRange(1000, 1);
    ASSERT_EQ(ranges.size(), 1u);
    EXPECT_EQ(ranges[0].i_begin, 0);
    EXPECT_EQ(ranges[0].i_count, 1000);
}

TEST(GpuDeviceSplit, EvenlyDivisibleSplitsUniformly) {
    // 100 particulas, 4 devices -> 25 cada uno
    auto ranges = splitParticleRange(100, 4);
    ASSERT_EQ(ranges.size(), 4u);
    int begin = 0;
    for (const auto& r : ranges) {
        EXPECT_EQ(r.i_begin, begin);
        EXPECT_EQ(r.i_count, 25);
        begin += r.i_count;
    }
    EXPECT_EQ(begin, 100);
}

TEST(GpuDeviceSplit, NonDivisibleDistributesRemainderToFirstDevices) {
    // 10 particulas, 3 devices -> 4, 3, 3 (el resto de 10%3=1 va al primer device)
    auto ranges = splitParticleRange(10, 3);
    ASSERT_EQ(ranges.size(), 3u);
    EXPECT_EQ(ranges[0].i_count, 4);
    EXPECT_EQ(ranges[1].i_count, 3);
    EXPECT_EQ(ranges[2].i_count, 3);

    EXPECT_EQ(ranges[0].i_begin, 0);
    EXPECT_EQ(ranges[1].i_begin, 4);
    EXPECT_EQ(ranges[2].i_begin, 7);
}

TEST(GpuDeviceSplit, RangesAreContiguousAndCoverAllParticles) {
    for (int n : {1, 2, 3, 7, 10, 17, 100, 257, 1000}) {
        for (int num_devices : {1, 2, 3, 4, 8}) {
            auto ranges = splitParticleRange(n, num_devices);
            int covered = 0;
            int expected_begin = 0;
            for (const auto& r : ranges) {
                EXPECT_EQ(r.i_begin, expected_begin)
                    << "n=" << n << " num_devices=" << num_devices;
                EXPECT_GE(r.i_count, 0);
                covered += r.i_count;
                expected_begin += r.i_count;
            }
            EXPECT_EQ(covered, n) << "n=" << n << " num_devices=" << num_devices;
        }
    }
}

TEST(GpuDeviceSplit, MoreDevicesThanParticlesClampsToOnePerParticle) {
    // 3 particulas, 8 devices pedidos -> como maximo 3 devices, cada uno con 1
    auto ranges = splitParticleRange(3, 8);
    ASSERT_EQ(ranges.size(), 3u);
    for (const auto& r : ranges) {
        EXPECT_EQ(r.i_count, 1);
    }
    EXPECT_EQ(ranges[0].i_begin, 0);
    EXPECT_EQ(ranges[1].i_begin, 1);
    EXPECT_EQ(ranges[2].i_begin, 2);
}

TEST(GpuDeviceSplit, NoDeviceGetsZeroParticlesWhenDevicesLETn) {
    // Invariante del diseno: mientras num_devices <= n, ningun device debe
    // quedar con i_count == 0 (evita lanzar kernels vacios).
    for (int n = 1; n <= 20; ++n) {
        for (int num_devices = 1; num_devices <= n; ++num_devices) {
            auto ranges = splitParticleRange(n, num_devices);
            for (const auto& r : ranges) {
                EXPECT_GT(r.i_count, 0)
                    << "n=" << n << " num_devices=" << num_devices;
            }
        }
    }
}

TEST(GpuDeviceSplit, MaxImbalanceIsAtMostOneParticle) {
    for (int n : {13, 100, 257, 1001}) {
        for (int num_devices : {2, 3, 4, 5, 7}) {
            auto ranges = splitParticleRange(n, num_devices);
            int min_count = ranges.empty() ? 0 : ranges[0].i_count;
            int max_count = min_count;
            for (const auto& r : ranges) {
                min_count = std::min(min_count, r.i_count);
                max_count = std::max(max_count, r.i_count);
            }
            EXPECT_LE(max_count - min_count, 1)
                << "n=" << n << " num_devices=" << num_devices;
        }
    }
}
