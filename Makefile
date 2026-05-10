CXX = g++
CXXFLAGS = -Wall -Wextra -O3 -fopenmp -std=c++17
TEST_CXXFLAGS = -Wall -Wextra -Wno-unknown-pragmas -O3 -fopenmp -std=c++17

TARGET = nbody_sim
SRCS = main.cpp Particle.cpp NBodySimulator.cpp Integrator.cpp Benchmark.cpp MetricsCalculator.cpp Visualizer.cpp
OBJS = $(SRCS:.cpp=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(OBJS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

benchmark: $(TARGET)
	./$(TARGET) --benchmark $(ARGS)

benchmark-all: $(TARGET)
	./$(TARGET) --benchmark-all $(ARGS)

analysis: $(TARGET)
	@echo "Ejecutando benchmarks completos..."
	./$(TARGET) --benchmark-all $(ARGS)
	@echo "Generando graficos de rendimiento..."
	python3 plot_performance.py

clean:
	rm -f $(OBJS) $(TARGET) *.dat run_tests *.png

TEST_TARGET = run_tests
TEST_SOURCES = tests/test_physics.cpp Particle.cpp NBodySimulator.cpp Integrator.cpp MetricsCalculator.cpp Visualizer.cpp

test: $(TEST_SOURCES)
	$(CXX) $(TEST_CXXFLAGS) -o $(TEST_TARGET) $(TEST_SOURCES) $(LDFLAGS) -lgtest -lgtest_main -pthread
	./$(TEST_TARGET)
