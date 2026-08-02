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

TARGET = nbody_sim
SRCS = main.cpp Particle.cpp NBodySimulator.cpp Integrator.cpp Benchmark.cpp MetricsCalculator.cpp Visualizer.cpp
OBJS = $(SRCS:.cpp=.o)

.PHONY: all benchmark benchmark-all analysis clean test test-cuda-buffer test-cuda-soa vec-report profile

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(OBJS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

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
	rm -f $(OBJS) $(TARGET) *.dat run_tests *.png vec_*.log

TEST_TARGET = run_tests
TEST_SOURCES = tests/test_physics.cpp tests/test_gpu_equivalence.cpp Particle.cpp NBodySimulator.cpp Integrator.cpp MetricsCalculator.cpp Visualizer.cpp

test: $(TEST_SOURCES)
	$(CXX) $(TEST_CXXFLAGS) -o $(TEST_TARGET) $(TEST_SOURCES) $(LDFLAGS) -lgtest -lgtest_main -pthread
	./$(TEST_TARGET)

test-cuda-buffer: tests/test_cuda_buffer.cpp CudaBuffer.h
	$(CXX) $(TEST_CXXFLAGS) -o run_test_cuda_buffer tests/test_cuda_buffer.cpp $(LDFLAGS)
	./run_test_cuda_buffer
	rm -f run_test_cuda_buffer

test-cuda-soa: tests/test_cuda_device_soa.cpp CudaDeviceSoA.h CudaBuffer.h
	$(CXX) $(TEST_CXXFLAGS) -o run_test_cuda_soa tests/test_cuda_device_soa.cpp $(LDFLAGS)
	./run_test_cuda_soa
	rm -f run_test_cuda_soa
