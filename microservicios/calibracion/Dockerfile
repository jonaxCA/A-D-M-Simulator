FROM epidemia/base-simulacion
COPY microservicios/calibracion/ /app/microservicios/calibracion/
COPY docs/contratos/calibracion/ /app/docs/contratos/calibracion/
USER epidemia
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
# La API; con CALIBRACION_TRABAJADOR=1 también el trabajador (microservicios/calibracion/__main__.py).
CMD ["python", "-m", "microservicios.calibracion"]
