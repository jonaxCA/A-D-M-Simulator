# Arranque del contenedor: lanza el sondeo en un hilo y sirve las rutas. Fuera de Docker:
#     python -m microservicios.estado_servicios 127.0.0.1:5262
import sys

from waitress import serve

from . import sondeo
from .app import app

sondeo.iniciar()
serve(app, listen=sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0:8000")
