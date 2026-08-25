FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copiar el código fuente
COPY civicmesh/ civicmesh/

ENTRYPOINT ["python", "-m", "civicmesh.node"]
