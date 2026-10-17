FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/microservicios/comun
COPY backend_web/ /app/backend_web/
COPY procesamiento/ /app/procesamiento/
COPY microservicios/comun/ /app/microservicios/comun/
COPY microservicios/pareto/ /app/microservicios/pareto/
COPY docs/contratos/pareto/ /app/docs/contratos/pareto/
RUN pip install --no-cache-dir -r backend_web/requerimientos.txt \
    -r procesamiento/requerimientos.txt \
    -r microservicios/comun/requirements.txt waitress==3.0.2 \
    && useradd --create-home --uid 10001 epidemia
USER epidemia
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "microservicios.pareto.app:app"]
