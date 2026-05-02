CXX = g++
CXXFLAGS = -Wall -Wextra -O3 -fopenmp -std=c++14
TEST_CXXFLAGS = -Wall -Wextra -Wno-unknown-pragmas -O3 -std=c++14

TARGET = nbody_sim
SRCS = main.cpp Particle.cpp NBodySimulator.cpp Integrator.cpp
OBJS = $(SRCS:.cpp=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(OBJS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET) state_*.dat run_tests

TEST_TARGET = run_tests
TEST_SOURCES = tests/test_physics.cpp Particle.cpp NBodySimulator.cpp Integrator.cpp

test: $(TEST_SOURCES)
	$(CXX) $(TEST_CXXFLAGS) -o $(TEST_TARGET) $(TEST_SOURCES) $(LDFLAGS) -lgtest -lgtest_main -pthread
	./$(TEST_TARGET)
