from functools import lru_cache

import xmlschema

from . import config

# Las raíces se repiten entre servicios con otro contenido (<corrida>, <intervencion>),
# así que el XSD se elige por servicio y raíz, igual que en microservicios/comun/tests/test_xsd.py.
POR_RESPUESTA = {
    ("corridas", "corrida"): "corridas/corrida.xsd",
    ("corridas", "listado"): "corridas/corrida.xsd",
    ("corridas", "equivalencia"): "corridas/corrida.xsd",
    ("corridas", "motores"): "corridas/corrida.xsd",
    ("parametros", "parametros"): "parametros/parametros.xsd",
    ("parametros", "versiones_parametros"): "parametros/parametros.xsd",
    ("parametros", "version_parametros"): "parametros/parametros.xsd",
    ("parametros", "ajustes_version"): "parametros/parametros.xsd",
    ("intervenciones", "intervenciones_version"): "intervenciones/intervencion.xsd",
    ("intervenciones", "intervencion"): "intervenciones/intervencion.xsd",
    ("aprobacion", "envio"): "aprobacion/aprobacion.xsd",
    ("aprobacion", "firma"): "aprobacion/aprobacion.xsd",
    ("comparacion", "comparacion"): "comparacion/comparacion.xsd",
    ("pareto", "pareto"): "pareto/pareto.xsd",
    ("pareto", "sensibilidad"): "pareto/pareto.xsd",
    ("pareto", "calibracion"): "pareto/pareto.xsd",
    ("resultados", "resultado"): "resultados/resultado.xsd",
    ("escenarios-xml", "escenario"): "escenarios-xml/escenario.xsd",
    ("enfermedades", "enfermedad"): "enfermedades/enfermedad.xsd",
    ("importacion", "serie_observada"): "importacion/serie_observada.xsd",
    **{("calibracion", raiz): "calibracion/calibracion.xsd" for raiz in (
        "calibracion", "calibraciones", "estado_calibracion", "evaluacion", "ajuste", "escenario_calibrado")},
}
PROBLEMA = "comun/error.xsd"
ESCENARIO = "escenarios-xml/escenario.xsd"


class XMLInvalido(Exception):
    def __init__(self, xsd, errores):
        self.xsd = xsd
        self.errores = errores
        super().__init__("%s: %s" % (xsd, "; ".join(e["mensaje"] for e in errores[:3])))


@lru_cache(maxsize=None)
def esquema(ruta):
    return xmlschema.XMLSchema(str(config.CONTRATOS / ruta))


def validar_con(ruta, contenido):
    errores = [{"ruta": e.path or "/", "mensaje": e.reason or str(e)}
               for e in esquema(ruta).iter_errors(contenido)]
    if errores:
        raise XMLInvalido(ruta.split("/")[-1], errores)


def xsd_de(servicio, raiz):
    return POR_RESPUESTA.get((servicio, raiz))


def validar_escenario(contenido):
    validar_con(ESCENARIO, contenido)
