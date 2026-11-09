import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

registro = logging.getLogger("epidemia.escritorio")


def configurar(carpeta):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / "actividad.log"
    manejador = RotatingFileHandler(archivo, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    registro.addHandler(manejador)
    registro.setLevel(logging.INFO)
    return archivo


def peticion(metodo, servicio, ruta, estado, correlacion, ms):
    registro.info("HTTP %s %s %s -> %s %.0f ms cid=%s", metodo, servicio, ruta, estado, ms, correlacion)


def validado(servicio, xsd):
    registro.info("XSD %s válido (%s)", xsd, servicio)


def accion(usuario, texto):
    registro.info("ACCION usuario=%s %s", usuario or "-", texto)


def error(texto):
    registro.warning("ERROR %s", texto)
