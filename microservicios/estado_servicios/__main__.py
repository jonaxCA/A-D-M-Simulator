# Arranque del contenedor: lanza el sondeo en un hilo y sirve las rutas. Fuera de Docker:
#     python -m microservicios.estado_servicios 127.0.0.1:5262
import sys

from epidemia_comun.servir import ESCUCHA, servir

from . import sondeo
from .app import app

sondeo.iniciar()
servir(app, sys.argv[1] if len(sys.argv) > 1 else ESCUCHA)
