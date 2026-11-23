# Arranque del contenedor. Con CALIBRACION_TRABAJADOR=1 (el contenedor calibracion-trabajador,
# que no publica su puerto) además cierra lo que quedó a medias y corre el trabajador en un hilo.
# Fuera de Docker:
#     python -m microservicios.calibracion 127.0.0.1:5246
import os
import sys
import threading

from epidemia_comun.servir import ESCUCHA, servir

from . import trabajador
from .app import app

if os.environ.get("CALIBRACION_TRABAJADOR") == "1":
    trabajador.recuperar()
    threading.Thread(target=trabajador.ciclo, args=(threading.Event(),),
                     name="trabajador", daemon=True).start()
servir(app, sys.argv[1] if len(sys.argv) > 1 else ESCUCHA)
