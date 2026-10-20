# Imagen base de los microservicios: Python, las dependencias y el código que todos
# comparten (backend_web, procesamiento y epidemia_comun). Cada servicio parte de aquí y
# solo copia su carpeta y su contrato. La construye el compose antes que los servicios.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/microservicios/comun

# Las dependencias van antes que el código: cambiar código no vuelve a instalarlas.
COPY backend_web/requerimientos.txt /tmp/requerimientos/backend_web.txt
COPY procesamiento/requerimientos.txt /tmp/requerimientos/procesamiento.txt
COPY microservicios/comun/requirements.txt /tmp/requerimientos/comun.txt
RUN pip install --no-cache-dir -r /tmp/requerimientos/backend_web.txt \
    -r /tmp/requerimientos/procesamiento.txt -r /tmp/requerimientos/comun.txt waitress==3.0.2 \
    && useradd --create-home --uid 10001 epidemia

COPY backend_web/ /app/backend_web/
COPY procesamiento/ /app/procesamiento/
COPY microservicios/comun/ /app/microservicios/comun/
USER epidemia
EXPOSE 8000
