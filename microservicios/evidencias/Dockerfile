FROM epidemia/base
COPY microservicios/evidencias/ /app/microservicios/evidencias/
COPY docs/contratos/evidencias/ /app/docs/contratos/evidencias/
# La carpeta de los archivos. El volumen del compose se monta aquí y, la primera vez, toma este
# dueño: sin él, el usuario epidemia no podría escribir.
USER root
RUN mkdir -p /var/lib/epidemia/evidencias && chown epidemia:epidemia /var/lib/epidemia/evidencias
USER epidemia
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "microservicios.evidencias.app:app"]
