# Imagen base de los servicios de F, vigilancia, analítica y plataforma (casos, sincronizacion,
# dispositivos, evidencias, vacunas, importacion, indicadores, series, zonas, notificaciones y
# estado-servicios), y de los de D que no usan el motor (evidencias, importacion, aprobacion,
# poblacion, tipos-intervencion, regiones, escenarios, escenarios-xml e intervenciones): solo Python
# y epidemia_comun. No lleva backend_web ni procesamiento (E8). La
# construye el compose antes que ellos.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/microservicios/comun

COPY microservicios/comun/requirements.txt /tmp/requerimientos/comun.txt
RUN pip install --no-cache-dir -r /tmp/requerimientos/comun.txt waitress==3.0.2 \
    && useradd --create-home --uid 10001 epidemia

COPY microservicios/comun/ /app/microservicios/comun/
USER epidemia
EXPOSE 8000
