"""Servicio dispositivos: registra, consulta y revoca los dispositivos de las apps.

Cada quien registra, ve y revoca los suyos; ADMINISTRADOR, los de todos. Las
reglas están en backend_web.dispositivos. Revocar es para siempre, y casos
deja de aceptar casos de ese dispositivo aunque el token siga vigente.
"""
from flask import g, request

from backend_web import dispositivos
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

ROLES = ("CAPTURISTA", "ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
LIMITE, LIMITE_MAX = 50, 200


def _es_admin():
    return "ADMINISTRADOR" in g.usuario.get("roles", [])


def _visible(device_id):
    """El dispositivo, si es de quien pregunta o pregunta ADMINISTRADOR. El de otra
    persona no existe para quien pregunta."""
    fila = dispositivos.get_dispositivo(entero_positivo(device_id, "id"))
    if fila is None or (fila["user_id"] != g.contexto.user_id and not _es_admin()):
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el dispositivo.")
    return fila


def registrar(app):
    @app.post("/api/v1/devices")
    @requiere_token(roles=ROLES)
    def alta():
        datos = diccionario(leer_cuerpo())
        errores = dispositivos.valida_dispositivo(datos)
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        fila, creado, conflicto = dispositivos.registrar_dispositivo(
            g.contexto.user_id, datos, contexto=g.contexto)
        if conflicto:
            raise ErrorAPI(409, "CONFLICTO", conflicto)
        return responder(fila, "dispositivo", estado=201 if creado else 200)

    @app.get("/api/v1/devices")
    @requiere_token(roles=ROLES)
    def listar():
        limite = request.args.get("limit")
        limite = LIMITE if limite is None else entero_positivo(limite, "limit")
        if limite > LIMITE_MAX:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "limit no puede pasar de %d." % LIMITE_MAX)
        usuario = request.args.get("user_id")
        if usuario is None:
            dueno = None if _es_admin() else g.contexto.user_id
        else:
            dueno = entero_positivo(usuario, "user_id")
            if dueno != g.contexto.user_id and not _es_admin():
                raise ErrorAPI(403, "PERMISO_INSUFICIENTE",
                               "Solo ADMINISTRADOR ve los dispositivos de otra cuenta.")
        filas = dispositivos.listar_dispositivos(dueno, limite)
        return responder({"total": len(filas), "dispositivos": filas}, "listado")

    @app.get("/api/v1/devices/<device_id>")
    @requiere_token(roles=ROLES)
    def consultar(device_id):
        return responder(_visible(device_id), "dispositivo")

    @app.post("/api/v1/devices/<device_id>/revoke")
    @requiere_token(roles=ROLES)
    def revocar(device_id):
        fila = _visible(device_id)
        revocado, error = dispositivos.revocar_dispositivo(
            fila["id"], contexto=g.contexto, user_id=None if _es_admin() else g.contexto.user_id)
        if error and error.startswith("No existe"):
            raise ErrorAPI(404, "NO_ENCONTRADO", error)
        if error:
            raise ErrorAPI(409, "CONFLICTO", error)
        return responder(revocado, "dispositivo")
