FROM epidemia/base
COPY microservicios/simulador/ /app/microservicios/simulador/
COPY docs/contratos/simulador/ /app/docs/contratos/simulador/
USER epidemia
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
# El trabajador y la ruta de estado en el mismo proceso (microservicios/simulador/__main__.py).
CMD ["python", "-m", "microservicios.simulador"]
