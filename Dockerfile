FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# instalar dependencias 
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    make \
    libomp-dev \
    libgtest-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# compilar
WORKDIR /usr/src/gtest
RUN cmake CMakeLists.txt && make && cp lib/*.a /usr/lib

WORKDIR /app

# copiar codigo fuente al contenedor
COPY . .

# compilar
RUN make clean && make

# ejecutar tests
CMD ["make", "test"]