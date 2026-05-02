CXX = g++
CXXFLAGS = -Wall -Wextra -O3 -fopenmp -std=c++17
TEST_CXXFLAGS = -Wall -Wextra -Wno-unknown-pragmas -O3 -std=c++17

TARGET = nbody_sim
SRCS = main.cpp Particle.cpp NBodySimulator.cpp Integrator.cpp Benchmark.cpp MetricsCalculator.cpp
OBJS = $(SRCS:.cpp=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(OBJS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Objetivo para ejecutar el benchmark automáticamente
benchmark: $(TARGET)
	./$(TARGET) --benchmark

# Objetivo para ejecutar el análisis (preparado para tu script de R)
analysis:
	@echo "Ejecutando analisis de datos..."
	# Rscript analisis_rendimiento.R

# Limpieza profunda que incluye los archivos de datos generados
clean:
	rm -f $(OBJS) $(TARGET) *.dat run_tests

TEST_TARGET = run_tests
TEST_SOURCES = tests/test_physics.cpp Particle.cpp NBodySimulator.cpp Integrator.cpp

test: $(TEST_SOURCES)
	$(CXX) $(TEST_CXXFLAGS) -o $(TEST_TARGET) $(TEST_SOURCES) $(LDFLAGS) -lgtest -lgtest_main -pthread
	./$(TEST_TARGET)
