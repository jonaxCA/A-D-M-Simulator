# Arranque del contenedor: cierra lo que quedó a medias, lanza el trabajador en un
# hilo y sirve /health y /api/v1/worker/status. Fuera de Docker:
#     python -m microservicios.simulador 127.0.0.1:5242
import sys
import threading

from waitress import serve

from . import trabajador
from .app import app

trabajador.recuperar()
threading.Thread(target=trabajador.ciclo, args=(app.config, threading.Event()),
                 name="trabajador", daemon=True).start()
serve(app, listen=sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0:8000")
