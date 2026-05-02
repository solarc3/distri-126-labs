CXX = g++
CXXFLAGS = -Wall -Wextra -O3 -fopenmp -std=c++14

TARGET = nbody_sim
SRCS = main.cpp Particle.cpp NBodySimulator.cpp
OBJS = $(SRCS:.cpp=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(OBJS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET) state_*.dat