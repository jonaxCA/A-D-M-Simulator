FROM epidemia/base-vigilancia
COPY microservicios/intervenciones/ /app/microservicios/intervenciones/
COPY docs/contratos/intervenciones/ /app/docs/contratos/intervenciones/
USER epidemia
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
CMD ["python", "-m", "epidemia_comun.servir", "microservicios.intervenciones.app:app"]
