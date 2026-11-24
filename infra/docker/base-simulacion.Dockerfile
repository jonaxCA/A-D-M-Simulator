# Imagen base de los servicios de simulación (corridas, simulador, resultados, comparacion,
# pareto y calibracion) y de los de D que usan el motor (enfermedades, parametros y validacion): Python, procesamiento y epidemia_comun. No lleva backend_web (E8). La construye el
# compose antes que ellos.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/microservicios/comun

COPY procesamiento/requerimientos.txt /tmp/requerimientos/procesamiento.txt
COPY microservicios/comun/requirements.txt /tmp/requerimientos/comun.txt
RUN pip install --no-cache-dir -r /tmp/requerimientos/procesamiento.txt \
    -r /tmp/requerimientos/comun.txt waitress==3.0.2 \
    && useradd --create-home --uid 10001 epidemia

COPY procesamiento/ /app/procesamiento/
COPY microservicios/comun/ /app/microservicios/comun/
USER epidemia
EXPOSE 8000
