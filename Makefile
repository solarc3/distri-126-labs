CXX = g++
CXXFLAGS = -Wall -Wextra -O3 -fopenmp -std=c++17

TARGET = nbody_sim
SRCS = main.cpp Particle.cpp NBodySimulator.cpp Benchmark.cpp MetricsCalculator.cpp
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

# Objetivo para pruebas unitarias (preparado para GoogleTest/Catch2)
test:
	@echo "Ejecutando pruebas..."
	# ./tests_bin

# Limpieza profunda que incluye los archivos de datos generados
clean:
	rm -f $(OBJS) $(TARGET) *.dat