CXX ?= g++

# On the c7a.48xlarge build on the target host and keep -march=native.
# That lets GCC/Clang emit the exact Zen 4 ISA available there, including AVX-512.
# For binaries that run on heterogeneous CPUs (Docker image for AWS Batch: g5 is
# Ice Lake, xigpu is Zen 3 — no AVX-512, a Zen 4 native binary SIGILLs), build with
# MARCH_FLAGS="-march=x86-64-v3". The Dockerfile does this for the baked-in binary;
# run_batch.sh recompiles with -march=native on the actual target at container start.
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
# Fatbinary: SASS nativo para cada GPU destino (g4dn=T4 sm_75, p4d=A100 sm_80,
# g5=A10G sm_86, H100=sm_90) + PTX de compute_90 para forward-compat vía JIT en
# hardware más nuevo. Un solo -arch=sm_XX haría que la misma imagen falle o caiga
# a JIT en las demás GPUs; sin ningún flag de arquitectura, nvcc emite PTX genérico
# y todo ejecuta vía JIT, lo que distorsiona los benchmarks.
# Para otro set de GPUs, override: make CUDA_GENCODE="-gencode arch=compute_90,code=sm_90"
CUDA_GENCODE ?= -gencode arch=compute_75,code=sm_75 \
                -gencode arch=compute_80,code=sm_80 \
                -gencode arch=compute_86,code=sm_86 \
                -gencode arch=compute_90,code=sm_90 \
                -gencode arch=compute_90,code=compute_90
# Los gencode van en la receta y no dentro de NVCCFLAGS: un override de NVCCFLAGS por
# línea de comandos (make NVCCFLAGS="...") anula las asignaciones del Makefile y los
# descartaría silenciosamente.
CUDA_HOME ?= /usr/local/cuda
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


.PHONY: all benchmark benchmark-all analysis clean test test-gpu test-cuda-buffer test-cuda-soa vec-report profile cuda-info benchmark-gpu

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(OBJS) $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

kernels/%.o: kernels/%.cu
	$(NVCC) $(NVCCFLAGS) $(CUDA_GENCODE) -c $< -o $@

cuda-info:
	@command -v $(NVCC) >/dev/null 2>&1 && $(NVCC) --version || \
		(echo "nvcc no encontrado: instala CUDA Toolkit o usa el Dockerfile CUDA del repo" && exit 1)

benchmark: $(TARGET)
	./$(TARGET) --benchmark $(ARGS)

benchmark-all: $(TARGET)
	./$(TARGET) --benchmark-all $(ARGS)
	@echo "Generando graficos de rendimiento..."
	python3 plot_performance.py

benchmark-gpu: $(TARGET)
	./$(TARGET) --benchmark-gpu $(ARGS)
	@echo "Generando graficos GPU..."
	python3 plot_gpu_benchmarks.py

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

test-gpu: $(TEST_SOURCES) $(CU_OBJS)
	@if [ -z "$(CUDA_KERNEL_FLAGS)" ]; then \
		echo "test-gpu requiere nvcc + kernels/*.cu (CUDA Toolkit); ejecuta 'make cuda-info' para diagnosticar."; \
		exit 1; \
	fi
	$(CXX) $(TEST_CXXFLAGS) $(CUDA_KERNEL_FLAGS) -o $(TEST_TARGET) $(TEST_SOURCES) $(CU_OBJS) $(LDFLAGS) -lgtest -lgtest_main -pthread
	./$(TEST_TARGET)

test-cuda-buffer: tests/test_cuda_buffer.cpp CudaBuffer.h
	$(CXX) $(TEST_CXXFLAGS) -o run_test_cuda_buffer tests/test_cuda_buffer.cpp $(LDFLAGS)
	./run_test_cuda_buffer
	rm -f run_test_cuda_buffer

test-cuda-soa: tests/test_cuda_device_soa.cpp CudaDeviceSoA.h CudaBuffer.h
	$(CXX) $(TEST_CXXFLAGS) -o run_test_cuda_soa tests/test_cuda_device_soa.cpp $(LDFLAGS)
	./run_test_cuda_soa
	rm -f run_test_cuda_soa
