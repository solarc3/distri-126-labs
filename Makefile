CXX ?= g++

# On the c7a.48xlarge build on the target host and keep -march=native.
# That lets GCC/Clang emit the exact Zen 4 ISA available there, including AVX-512.
MARCH_FLAGS ?= -march=native
OPT_FLAGS ?= -O3 -fno-math-errno
EXTRA_CXXFLAGS ?=
WARN_FLAGS ?= -Wall -Wextra
OMP_FLAGS ?= -fopenmp
STD_FLAGS ?= -std=c++17

CXXFLAGS = $(WARN_FLAGS) $(OPT_FLAGS) $(OMP_FLAGS) $(STD_FLAGS) $(MARCH_FLAGS) $(EXTRA_CXXFLAGS)
TEST_CXXFLAGS = $(WARN_FLAGS) -Wno-unknown-pragmas $(OPT_FLAGS) $(OMP_FLAGS) $(STD_FLAGS) $(MARCH_FLAGS) $(EXTRA_CXXFLAGS)

# CUDA: kernels/*.cu se compilan con nvcc y se linkean junto a los
# objetos C++ solo cuando existen. Sin kernels, el build sigue siendo 100% CPU/g++.
NVCC ?= nvcc
NVCCFLAGS ?= -O3 -std=c++17 -Xcompiler -Wall,-Wextra
CUDA_ARCH ?= sm_80
NVCCFLAGS += -arch=$(CUDA_ARCH)
CU_SOURCES := $(wildcard kernels/*.cu)
CU_OBJS := $(CU_SOURCES:.cu=.o)
NVCC_AVAILABLE := $(shell command -v $(NVCC) >/dev/null 2>&1 && echo 1 || echo 0)

TARGET = nbody_sim
SRCS = main.cpp Particle.cpp NBodySimulator.cpp Integrator.cpp Benchmark.cpp MetricsCalculator.cpp Visualizer.cpp
OBJS = $(SRCS:.cpp=.o)

TEST_OBJS =

ifneq ($(CU_SOURCES),)
ifeq ($(NVCC_AVAILABLE),1)
# Derivar CUDA_HOME de la ubicación real de nvcc (ej. /usr/local/cuda/bin/nvcc ->
# /usr/local/cuda) en vez de asumir una ruta fija; con fallback razonable si falla.
CUDA_HOME := $(patsubst %/,%,$(dir $(patsubst %/,%,$(dir $(shell command -v $(NVCC))))))
ifeq ($(CUDA_HOME),)
CUDA_HOME := /usr/local/cuda
endif
OBJS += $(CU_OBJS)
CXXFLAGS += -DNBODY_ENABLE_CUDA_KERNELS -I$(CUDA_HOME)/include
TEST_CXXFLAGS += -DNBODY_ENABLE_CUDA_KERNELS -I$(CUDA_HOME)/include
TEST_OBJS += $(CU_OBJS)
LDFLAGS += -L$(CUDA_HOME)/lib64 -lcudart
else
$(warning CUDA kernels found but '$(NVCC)' is not available; building CPU-only target)
endif
endif


.PHONY: all benchmark benchmark-all analysis clean test test-cuda-buffer test-cuda-soa vec-report profile cuda-info

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(OBJS) $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

kernels/%.o: kernels/%.cu
	$(NVCC) $(NVCCFLAGS) -c $< -o $@

cuda-info:
	@command -v $(NVCC) >/dev/null 2>&1 && $(NVCC) --version || \
		(echo "nvcc no encontrado: instala CUDA Toolkit o usa el Dockerfile CUDA del repo" && exit 1)

benchmark: $(TARGET)
	./$(TARGET) --benchmark $(ARGS)

benchmark-all: $(TARGET)
	./$(TARGET) --benchmark-all $(ARGS)
	@echo "Generando graficos de rendimiento..."
	python3 plot_performance.py

analysis: $(TARGET)
	@echo "Ejecutando benchmarks completos..."
	./$(TARGET) --benchmark-all $(ARGS)
	@echo "Generando graficos de rendimiento..."
	python3 plot_performance.py

# Ejemplo:
#   make vec-report MARCH_FLAGS="-march=native"
# Los mensajes dicen que loops se vectorizaron y por qué otros no.
vec-report:
	$(MAKE) clean
	$(MAKE) EXTRA_CXXFLAGS="-fopt-info-vec-optimized -fopt-info-vec-missed"

# Build útil para perf/flamegraph: conserva símbolos y frame pointers.
profile: EXTRA_CXXFLAGS += -g -fno-omit-frame-pointer
profile: clean $(TARGET)

clean:
	rm -f $(OBJS) $(CU_OBJS) $(TARGET) *.dat run_tests *.png vec_*.log

TEST_TARGET = run_tests
TEST_SOURCES = tests/test_physics.cpp tests/test_gpu_equivalence.cpp Particle.cpp NBodySimulator.cpp Integrator.cpp MetricsCalculator.cpp Visualizer.cpp

test: $(TEST_SOURCES) $(TEST_OBJS)
	$(CXX) $(TEST_CXXFLAGS) -o $(TEST_TARGET) $(TEST_SOURCES) $(TEST_OBJS) $(LDFLAGS) -lgtest -lgtest_main -pthread
	./$(TEST_TARGET)

test-cuda-buffer: tests/test_cuda_buffer.cpp CudaBuffer.h
	$(CXX) $(TEST_CXXFLAGS) -o run_test_cuda_buffer tests/test_cuda_buffer.cpp $(LDFLAGS)
	./run_test_cuda_buffer
	rm -f run_test_cuda_buffer

test-cuda-soa: tests/test_cuda_device_soa.cpp CudaDeviceSoA.h CudaBuffer.h
	$(CXX) $(TEST_CXXFLAGS) -o run_test_cuda_soa tests/test_cuda_device_soa.cpp $(LDFLAGS)
	./run_test_cuda_soa
	rm -f run_test_cuda_soa
