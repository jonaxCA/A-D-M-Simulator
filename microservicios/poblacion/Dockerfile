FROM epidemia/base-vigilancia
COPY microservicios/poblacion/ /app/microservicios/poblacion/
COPY docs/contratos/poblacion/ /app/docs/contratos/poblacion/
USER epidemia
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
CMD ["python", "-m", "epidemia_comun.servir", "microservicios.poblacion.app:app"]
