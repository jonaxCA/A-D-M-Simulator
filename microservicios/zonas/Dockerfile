FROM epidemia/base
COPY microservicios/zonas/ /app/microservicios/zonas/
COPY docs/contratos/zonas/ /app/docs/contratos/zonas/
# Los municipios de cada jurisdicción sanitaria (jurisdicciones.py) y su geometría oficial
# (geometria.py), F7.
COPY datos/geo/nl_jurisdicciones_sanitarias.json datos/geo/nl_municipios.geojson /app/datos/geo/
USER epidemia
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
CMD ["python", "-m", "epidemia_comun.servir", "microservicios.zonas.app:app"]
