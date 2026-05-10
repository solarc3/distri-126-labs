FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    make \
    libomp-dev \
    libgtest-dev \
    cmake \
    python3 \
    python3-pip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir numpy matplotlib

RUN cd /usr/src/gtest \
    && cmake CMakeLists.txt \
    && make \
    && cp lib/*.a /usr/lib \
    && rm -rf /usr/src/gtest/*

RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /home/appuser/app

COPY --chown=appuser:appuser Makefile ./
COPY --chown=appuser:appuser *.h *.cpp ./
COPY --chown=appuser:appuser tests/       tests/
COPY --chown=appuser:appuser plot_performance.py ./

USER appuser
RUN make clean && make

CMD ["make", "test"]
