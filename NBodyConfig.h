#ifndef NBODY_CONFIG_H
#define NBODY_CONFIG_H

#include <cstddef>

namespace nbody_config {
constexpr std::size_t CACHE_LINE_BYTES = 64;
constexpr std::size_t DOUBLES_PER_CACHE_LINE = CACHE_LINE_BYTES / sizeof(double);

#ifndef NBODY_SOA_I_TILE
constexpr int SOA_I_TILE = 8;
#else
constexpr int SOA_I_TILE = NBODY_SOA_I_TILE;
#endif

#ifndef NBODY_SOA_J_TILE
constexpr int SOA_J_TILE = 4096;
#else
constexpr int SOA_J_TILE = NBODY_SOA_J_TILE;
#endif
}  // namespace nbody_config

#if defined(__GNUC__) || defined(__clang__)
#define NBODY_RESTRICT __restrict__
#else
#define NBODY_RESTRICT
#endif

#endif
