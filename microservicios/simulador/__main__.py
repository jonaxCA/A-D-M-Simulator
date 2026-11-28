# Arranque del contenedor: cierra lo que quedó a medias, lanza el trabajador y su latido (lo
# que lee estado-servicios) en dos hilos y sirve /health y /api/v1/worker/status. Fuera de Docker:
#     python -m microservicios.simulador 127.0.0.1:5242
import sys
import threading

from epidemia_comun.servir import ESCUCHA, servir

from . import trabajador
from .app import app

trabajador.recuperar()
detener = threading.Event()
threading.Thread(target=trabajador.ciclo, args=(app.config, detener),
                 name="trabajador", daemon=True).start()
threading.Thread(target=trabajador.latir, args=(detener,), name="latido", daemon=True).start()
servir(app, sys.argv[1] if len(sys.argv) > 1 else ESCUCHA)
