"""Servicio notificaciones: los avisos de cada persona para las apps.

Leer y marcar como leída es para quien inició sesión, y solo con sus propios
avisos. Crearlos es una ruta interna: la llaman simulador y aprobacion con un
token de servicio.
"""
from flask import g, request

from backend_web import notificaciones
from backend_web.contexto import Contexto
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token, solo_servicios
from epidemia_comun.validaciones import diccionario, entero_positivo

LIMITE, LIMITE_MAX = 50, 200
CAMPOS = {"user_id", "type", "title", "body", "payload"}


def _solo_no_leidas(valor):
    if valor is None:
        return False
    if valor.lower() not in ("true", "false"):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "unread debe ser true o false.")
    return valor.lower() == "true"


def registrar(app):
    @app.get("/api/v1/notifications")
    @requiere_token()
    def listar():
        limite = request.args.get("limit")
        limite = LIMITE if limite is None else entero_positivo(limite, "limit")
        if limite > LIMITE_MAX:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "limit no puede pasar de %d." % LIMITE_MAX)
        filas, no_leidas = notificaciones.listar_notificaciones(
            g.contexto.user_id, _solo_no_leidas(request.args.get("unread")), limite)
        return responder({"total": len(filas), "no_leidas": no_leidas, "notificaciones": filas},
                         "bandeja")

    @app.post("/api/v1/notifications/<notificacion_id>/read")
    @requiere_token()
    def leer(notificacion_id):
        fila, error = notificaciones.marcar_leida(entero_positivo(notificacion_id, "id"),
                                                  g.contexto.user_id, contexto=g.contexto)
        if error:
            raise ErrorAPI(404, "NO_ENCONTRADO", error)
        return responder(fila, "notificacion")

    @app.post("/api/v1/notifications")
    @solo_servicios
    def crear():
        cuerpo = diccionario(leer_cuerpo())
        desconocidos = set(cuerpo) - CAMPOS
        if desconocidos:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "Campos no reconocidos: " + ", ".join(sorted(desconocidos)))
        # En XML sin tipo="numero" el id llega como texto.
        datos = dict(cuerpo, user_id=entero_positivo(cuerpo.get("user_id"), "user_id"))
        # No hay persona detrás: la bitácora registra qué servicio lo pidió.
        contexto = Contexto(None, request.remote_addr, ("servicio " + g.servicio["sub"])[:255])
        notificacion_id, error = notificaciones.crear_notificacion(datos, contexto=contexto)
        if error and error.startswith("No existe"):
            raise ErrorAPI(404, "NO_ENCONTRADO", error)
        if error:
            raise ErrorAPI(422, "DATOS_INVALIDOS", error)
        return responder({"id": notificacion_id, "user_id": datos["user_id"], "type": datos["type"]},
                         "notificacion", estado=201)
