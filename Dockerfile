FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Instalar el paquete con el código presente para que setuptools incluya
# civicmesh en la imagen, en vez de depender del directorio de trabajo.
COPY pyproject.toml ./
COPY civicmesh/ civicmesh/
RUN pip install --no-cache-dir .

# Recursos usados por los entrypoints de publicadores y analítica.
COPY generadores.example.yaml ./
COPY data/air_quality/ data/air_quality/
COPY scripts/frontend.py scripts/frontend.py

ENTRYPOINT ["python", "-m", "civicmesh.node"]
