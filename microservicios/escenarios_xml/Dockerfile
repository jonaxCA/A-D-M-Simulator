FROM epidemia/base
COPY microservicios/escenarios_xml/ /app/microservicios/escenarios_xml/
# openapi.json y escenario.xsd (el servicio publica el XSD y valida contra él)
COPY docs/contratos/escenarios-xml/ /app/docs/contratos/escenarios-xml/
USER epidemia
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "microservicios.escenarios_xml.app:app"]
