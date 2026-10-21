FROM epidemia/base
COPY microservicios/estado_servicios/ /app/microservicios/estado_servicios/
COPY docs/contratos/estado-servicios/ /app/docs/contratos/estado-servicios/
USER epidemia
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
# El sondeo y las rutas en el mismo proceso (microservicios/estado_servicios/__main__.py).
CMD ["python", "-m", "microservicios.estado_servicios"]
