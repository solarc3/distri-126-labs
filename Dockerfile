FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    make \
    libomp-dev \
    libgtest-dev \
    cmake \
    numactl \
    hwloc \
    python3 \
    python3-pip \
    ca-certificates \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws/

RUN pip3 install --no-cache-dir numpy matplotlib

RUN cd /usr/src/gtest \
    && cmake CMakeLists.txt \
    && make \
    && cp lib/*.a /usr/lib \
    && rm -rf /usr/src/gtest/*

RUN nvcc --version

RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /home/appuser/app

COPY --chown=appuser:appuser Makefile ./
COPY --chown=appuser:appuser *.h *.cpp ./
COPY --chown=appuser:appuser tests/       tests/
COPY --chown=appuser:appuser kernels/     kernels/
COPY --chown=appuser:appuser plot_performance.py ./
COPY --chown=appuser:appuser plot_gpu_benchmarks.py ./
COPY --chown=appuser:appuser run_batch.sh ./

RUN chown -R appuser:appuser /home/appuser/app
RUN chmod +x /home/appuser/app/run_batch.sh

USER appuser
# Build portable: la imagen corre en CPUs heterogéneas (AWS Batch g5/g4dn/p4d, xigpu),
# así que el binario horneado no puede usar -march=native (SIGILL fuera del build host).
# run_batch.sh recompila con -march=native al iniciar el contenedor.
RUN make clean && make MARCH_FLAGS="-march=x86-64-v3"

CMD ["./run_batch.sh"]
