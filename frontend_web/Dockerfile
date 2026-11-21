# La web (D36) en contenedor, para la nube (F1). Parte de epidemia/base, que ya trae Flask,
# waitress, backend_web, procesamiento y epidemia_comun: solo agrega frontend_web. En local se
# puede seguir corriendo fuera de Docker con python -m frontend_web.run.
FROM epidemia/base
COPY frontend_web/ /app/frontend_web/
USER epidemia
# /health no toca la base ni los servicios: dice que el proceso responde.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)" || exit 1
CMD ["python", "-m", "epidemia_comun.servir", "frontend_web.run:app"]
