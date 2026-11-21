from flask import g, request

from epidemia_comun import cache
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo
from backend_web import queries
from backend_web.audit import log_audit
from backend_web.db import query

LIMITE_MAXIMO = 20
TTL_CACHE = 60
ESTADO_NL = "19"
DIAS_CURVA = 30


def curva(dias=DIAS_CURVA):
    # Casos por día de todas las enfermedades en los municipios de Nuevo León.
    filas = query("""SELECT c.report_date::text AS fecha, count(*) AS total
                     FROM cases c JOIN regions r ON r.id = c.region_id
                     WHERE r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
                       AND c.report_date >= current_date - (%s || ' days')::interval
                     GROUP BY c.report_date ORDER BY c.report_date""", (ESTADO_NL, dias - 1))
    return [{"fecha": f["fecha"], "total": f["total"]} for f in filas]


def _limite():
    limite = entero_positivo(request.args.get("limit", "5"), "limit")
    if limite > LIMITE_MAXIMO:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "limit no puede ser mayor que %d." % LIMITE_MAXIMO)
    return limite


def registrar(app):
    # Públicas, como el dashboard del monolito, que se ve sin iniciar sesión.
    @app.get("/api/v1/dashboard/indicators")
    def indicadores():
        datos = cache.obtener("indicadores", "indicators", TTL_CACHE,
                              queries.get_resumen_indicadores)
        return responder(datos, "indicadores")

    @app.get("/api/v1/dashboard/situation")
    def situacion():
        limite = _limite()
        filas = cache.obtener("indicadores", "situation:limit=%d" % limite, TTL_CACHE,
                              lambda: queries.get_resumen_situacion(limit=limite))
        return responder({"enfermedades": filas}, "situacion")

    # La curva del tablero público: agregada, sin datos de personas.
    @app.get("/api/v1/dashboard/curve")
    def curva_epidemica():
        puntos = cache.obtener("indicadores", "curve:days=%d" % DIAS_CURVA, TTL_CACHE, curva)
        return responder({"dias": DIAS_CURVA, "puntos": puntos}, "curva")

    # El mismo resumen, para exportarlo: pide sesión para que la bitácora sepa quién exportó.
    @app.get("/api/v1/dashboard/situation/export")
    @requiere_token()
    def exportar_situacion():
        limite = _limite()
        filas = queries.get_resumen_situacion(limit=limite)
        log_audit(g.contexto, "EXPORT", "reports", entity_id="resumen_situacion")
        return responder({"enfermedades": filas}, "situacion")
