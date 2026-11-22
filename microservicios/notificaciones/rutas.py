"""Servicio notificaciones: los avisos de cada persona para las apps.

Leer y marcar como leída es para quien inició sesión, y solo con sus propios
avisos. Crearlos es una ruta interna: la llaman simulador, aprobacion, sincronizacion y
estado-servicios con un token de servicio.
"""
from flask import g, request

from epidemia_comun.auditoria import Contexto
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token, solo_servicios
from epidemia_comun.validaciones import diccionario, entero_positivo

from . import almacen

LIMITE, LIMITE_MAX = 50, 200
CAMPOS = {"user_id", "role", "type", "title", "body", "payload"}
# EPIDEMIOLOGO: escenarios por aprobar y casos nuevos. ADMINISTRADOR: alertas técnicas de
# estado-servicios (F7). CAPTURISTA: campañas (D49).
ROLES_DESTINO = ("EPIDEMIOLOGO", "ADMINISTRADOR", "CAPTURISTA")


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
        filas, no_leidas = almacen.listar_notificaciones(
            g.contexto.user_id, _solo_no_leidas(request.args.get("unread")), limite)
        return responder({"total": len(filas), "no_leidas": no_leidas, "notificaciones": filas},
                         "bandeja")

    @app.post("/api/v1/notifications/<notificacion_id>/read")
    @requiere_token()
    def leer(notificacion_id):
        fila, error = almacen.marcar_leida(entero_positivo(notificacion_id, "id"),
                                           g.contexto.user_id, contexto=g.contexto)
        if error:
            raise ErrorAPI(404, "NO_ENCONTRADO", error)
        return responder(fila, "notificacion")

    # Preferencias (D49): cada persona apaga los avisos que le tocan por su perfil, menos SYSTEM.
    @app.get("/api/v1/notifications/preferences")
    @requiere_token()
    def preferencias():
        return responder({"preferencias": almacen.preferencias(
            g.contexto.user_id, g.usuario.get("roles") or [])}, "preferencias")

    @app.put("/api/v1/notifications/preferences")
    @requiere_token()
    def guarda_preferencias():
        cuerpo = diccionario(leer_cuerpo())
        roles = g.usuario.get("roles") or []
        suyos = almacen.tipos_de(roles)
        if not cuerpo:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Manda al menos un tipo de aviso: {tipo: true o false}.")
        cambios, errores = {}, []
        for tipo, valor in cuerpo.items():
            if tipo not in suyos:
                errores.append("%s no es un aviso que te llegue." % tipo)
            elif tipo in almacen.FIJOS:
                errores.append("%s no se puede apagar." % tipo)
            elif valor in (True, "true"):
                cambios[tipo] = True
            elif valor in (False, "false"):
                cambios[tipo] = False
            else:
                errores.append("%s va con true o false." % tipo)
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        almacen.guarda_preferencias(g.contexto.user_id, cambios, contexto=g.contexto)
        return responder({"preferencias": almacen.preferencias(g.contexto.user_id, roles)},
                         "preferencias")

    @app.post("/api/v1/notifications")
    @solo_servicios
    def crear():
        cuerpo = diccionario(leer_cuerpo())
        desconocidos = set(cuerpo) - CAMPOS
        if desconocidos:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "Campos no reconocidos: " + ", ".join(sorted(desconocidos)))
        # No hay persona detrás: la bitácora registra qué servicio lo pidió.
        contexto = Contexto(None, request.remote_addr, ("servicio " + g.servicio["sub"])[:255])
        if "role" in cuerpo:
            if "user_id" in cuerpo:
                raise ErrorAPI(422, "DATOS_INVALIDOS", "Manda user_id o role, no los dos.")
            if cuerpo["role"] not in ROLES_DESTINO:
                raise ErrorAPI(422, "DATOS_INVALIDOS",
                               "role debe ser uno de: %s." % ", ".join(ROLES_DESTINO))
            datos = {k: v for k, v in cuerpo.items() if k != "role"}
            ids, error = almacen.crear_notificaciones_a_rol(datos, cuerpo["role"],
                                                            contexto=contexto)
            if error:
                raise ErrorAPI(422, "DATOS_INVALIDOS", error)
            return responder({"role": cuerpo["role"], "type": datos["type"], "total": len(ids)},
                             "notificacion", estado=201)
        # En XML sin tipo="numero" el id llega como texto.
        datos = dict(cuerpo, user_id=entero_positivo(cuerpo.get("user_id"), "user_id"))
        notificacion_id, error = almacen.crear_notificacion(datos, contexto=contexto)
        if error and error.startswith("No existe"):
            raise ErrorAPI(404, "NO_ENCONTRADO", error)
        if error:
            raise ErrorAPI(422, "DATOS_INVALIDOS", error)
        if notificacion_id is None:
            # La persona apagó ese tipo de aviso (D49): no es un error de quien avisa.
            return responder({"id": None, "user_id": datos["user_id"], "type": datos["type"],
                              "omitida": True}, "notificacion")
        return responder({"id": notificacion_id, "user_id": datos["user_id"], "type": datos["type"]},
                         "notificacion", estado=201)
