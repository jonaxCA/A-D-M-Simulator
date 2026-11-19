"""Cliente HTTP de la web hacia los microservicios (D36).

La web deja de ir a PostgreSQL y a Redis: cada dato lo pide al servicio dueño, en JSON, con el
JWT de la sesión (D34) y un X-Correlation-ID. La URL de cada servicio sale de
SERVICIO_<NOMBRE>_URL (p. ej. SERVICIO_ESCENARIOS_URL); si no viene, la del catálogo en local.
Detrás de nginx (D25) apunta a https://<dominio>/<servicio>. No reintenta escrituras.
"""
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

# Los puertos del catálogo (docs/arquitectura/microservicios.md).
PUERTOS = {"auth": 5201, "sesiones": 5202, "usuarios": 5203, "roles": 5204,
           "enfermedades": 5211, "parametros": 5212, "regiones": 5213, "poblacion": 5214,
           "tipos-intervencion": 5215, "casos": 5221, "sincronizacion": 5222,
           "escenarios": 5231, "intervenciones": 5232, "aprobacion": 5233, "validacion": 5234,
           "escenarios-xml": 5235, "corridas": 5241, "simulador": 5242, "resultados": 5243,
           "comparacion": 5244, "pareto": 5245, "indicadores": 5251, "series": 5252,
           "zonas": 5253, "notificaciones": 5261, "estado-servicios": 5262}
TIEMPO_ESPERA = 5


class ServicioNoDisponible(Exception):
    """El servicio no respondió, tardó demasiado o respondió 5xx."""

    def __init__(self, servicio):
        super().__init__(servicio)
        self.servicio = servicio


class ErrorServicio(Exception):
    """El servicio respondió un error 4xx (RFC 7807): estado, codigo y detalle."""

    def __init__(self, servicio, estado, codigo=None, detalle=None):
        super().__init__("%s %s %s" % (servicio, estado, codigo))
        self.servicio, self.estado, self.codigo, self.detalle = servicio, estado, codigo, detalle


def url_base(servicio):
    variable = "SERVICIO_%s_URL" % servicio.upper().replace("-", "_")
    return (os.environ.get(variable) or "http://localhost:%d" % PUERTOS[servicio]).rstrip("/")


def llamar(servicio, metodo, ruta, token=None, params=None, cuerpo=None, correlacion=None):
    """El JSON de la respuesta. Levanta ErrorServicio (4xx) o ServicioNoDisponible."""
    consulta = dict(params or {}, format="json")
    consulta = {k: v for k, v in consulta.items() if v is not None}
    url = "%s%s?%s" % (url_base(servicio), ruta, urllib.parse.urlencode(consulta))
    cabeceras = {"Accept": "application/json"}
    if token:
        cabeceras["Authorization"] = "Bearer " + token
    if correlacion:
        cabeceras["X-Correlation-ID"] = correlacion
    datos = None
    if cuerpo is not None:
        datos = json.dumps(cuerpo, default=str).encode("utf-8")
        cabeceras["Content-Type"] = "application/json"
    peticion = urllib.request.Request(url, data=datos, headers=cabeceras, method=metodo.upper())
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA) as respuesta:
            contenido = respuesta.read()
            return json.loads(contenido) if contenido else None
    except urllib.error.HTTPError as error:
        if error.code >= 500:
            log.warning("%s respondió %s en %s %s", servicio, error.code, metodo.upper(), ruta)
            raise ServicioNoDisponible(servicio) from error
        try:
            problema = json.loads(error.read() or b"{}")
        except ValueError:
            problema = {}
        raise ErrorServicio(servicio, error.code, problema.get("codigo"),
                            problema.get("detail")) from error
    except (OSError, ValueError) as error:
        log.warning("%s no responde en %s %s: %s", servicio, metodo.upper(), ruta, error)
        raise ServicioNoDisponible(servicio) from error
