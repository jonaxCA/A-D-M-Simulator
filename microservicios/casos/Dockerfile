FROM epidemia/base
COPY microservicios/casos/ /app/microservicios/casos/
COPY docs/contratos/casos/ /app/docs/contratos/casos/
USER epidemia
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "microservicios.casos.app:app"]
