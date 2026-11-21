import os
import time
import uuid

import jwt
from flask import current_app, g, request

from epidemia_comun.auditoria import Contexto, log_audit
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.redis_compartido import RedisNoDisponible
from epidemia_comun.seguridad import requiere_token, solo_servicios
from epidemia_comun.validaciones import diccionario, entero_positivo
from . import almacen as sesiones, dispositivos

ACCESS_TTL = 20 * 60
# Lo mismo que la cookie del monolito; renovar no alarga la sesión.
SESION_TTL = 8 * 60 * 60
# Supuesto (D41): tope de sesiones abiertas por cuenta; se cambia con el entorno.
MAX_SESIONES = 3
ADMIN = "ADMINISTRADOR"
ERRORES_CAMBIO = {
    "NO_ENCONTRADO": (404, "NO_ENCONTRADO", "No existe el dispositivo."),
    "SOLO_ADMIN": (403, "PERMISO_INSUFICIENTE", "Solo ADMINISTRADOR vuelve a autorizar un dispositivo revocado."),
    "SIN_CAMBIO": (409, "CONFLICTO", "El dispositivo ya está en ese estado."),
}


def _max_sesiones():
    crudo = os.environ.get("MAX_SESIONES_POR_USUARIO")
    if crudo:
        try:
            if int(crudo) >= 1:
                return int(crudo)
        except ValueError:
            pass
        current_app.logger.warning("MAX_SESIONES_POR_USUARIO=%r no es un entero >= 1; se usa %d.",
                                   crudo, MAX_SESIONES)
    return MAX_SESIONES


def _cambiar(id, estado, antes_de_guardar=None):
    # D41: quien no es ADMINISTRADOR solo cambia dispositivos desde una sesión abierta en uno autorizado.
    if ADMIN not in g.usuario["roles"]:
        huella = sesiones.dispositivo_de(g.usuario["sid"])
        if not huella or not dispositivos.autorizado(g.contexto.user_id, huella):
            raise ErrorAPI(403, "DISPOSITIVO_NO_AUTORIZADO",
                           "Esta sesión no se abrió desde un dispositivo autorizado.")
    ficha, error = dispositivos.cambiar(
        g.contexto, entero_positivo(id), ADMIN in g.usuario["roles"], estado, antes_de_guardar)
    if error:
        raise ErrorAPI(*ERRORES_CAMBIO[error])
    return responder(ficha, "dispositivo")


def emitir_access(usuario_id, roles, sid, ajustes):
    # Los mismos claims que firma auth al iniciar sesión.
    ahora = int(time.time())
    claims = {"iss": ajustes["JWT_ISSUER"], "aud": ajustes["JWT_AUDIENCE"],
              "sub": str(usuario_id), "roles": list(roles), "sid": sid,
              "jti": str(uuid.uuid4()), "iat": ahora, "nbf": ahora, "exp": ahora + ACCESS_TTL}
    return jwt.encode(claims, ajustes["JWT_SECRET_KEY"], algorithm="HS256")


def registrar(app):
    @app.errorhandler(RedisNoDisponible)
    def redis_caido(exc):
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible."))

    @app.errorhandler(sesiones.RefreshReutilizado)
    def refresh_reutilizado(exc):
        return respuesta_error(ErrorAPI(401, "TOKEN_REVOCADO", str(exc)))

    # Pública: quien renueva ya no tiene un access vigente; el refresh es la credencial.
    @app.post("/api/v1/sessions/refresh")
    def refresh():
        datos = diccionario(leer_cuerpo())
        refresh_token = datos.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Falta el campo refresh_token.")
        sesion = sesiones.renovar(refresh_token.strip())
        if sesion is None:
            raise ErrorAPI(401, "TOKEN_INVALIDO", "El refresh no es válido o la sesión venció.")
        return responder({
            "access_token": emitir_access(sesion["usuario"], sesion["roles"], sesion["sid"],
                                          current_app.config),
            "refresh_token": sesion["refresh"],
            "token_type": "Bearer",
            "expires_in": ACCESS_TTL,
            "sesion_expira": sesion["expira"],
        }, "sesion")

    @app.post("/api/v1/sessions/logout")
    @requiere_token()
    def logout():
        sesiones.revocar(g.usuario["jti"], g.usuario["exp"])
        sesiones.cerrar(g.usuario["sid"])
        log_audit(g.contexto, "LOGOUT", "users", entity_id=g.usuario["sub"])
        return responder({"cerrada": True}, "sesion")

    @app.get("/api/v1/sessions/current")
    @requiere_token()
    def actual():
        sesion = sesiones.obtener(g.usuario["sid"])
        if sesion is None:
            raise ErrorAPI(401, "TOKEN_REVOCADO", "La sesión ya no está activa.")
        return responder({**sesion, "access_expira": g.usuario["exp"]}, "sesion")

    # Interna: la llaman usuarios y roles al desactivar una cuenta o quitarle un rol.
    @app.delete("/api/v1/sessions/user/<id>")
    @solo_servicios("usuarios", "roles")
    def cerrar_de_usuario(id):
        usuario = entero_positivo(id)
        return responder({"usuario": usuario, "cerradas": sesiones.cerrar_todas(usuario)},
                         "sesiones_cerradas")

    # Interna: auth la llama cuando ya validó credenciales (y MFA); aquí se abre y se aplica el tope.
    @app.post("/api/v1/sessions/internal/open")
    @solo_servicios("auth")
    def abrir():
        datos = diccionario(leer_cuerpo())
        usuario = entero_positivo(datos.get("usuario"), "usuario")
        roles = datos.get("roles")
        if not isinstance(roles, list) or any(not isinstance(r, str) for r in roles):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "roles debe ser una lista de textos.")
        dispositivo = datos.get("dispositivo")
        if dispositivo is not None and not isinstance(dispositivo, str):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "dispositivo debe ser texto.")
        sesion = sesiones.abrir(usuario, roles, SESION_TTL, dispositivo or None, _max_sesiones())
        return responder({"sid": sesion["sid"], "refresh": sesion["refresh"],
                          "expira": sesion["expira"], "cerradas": sesion["cerradas"]}, "sesion")

    # Interna: auth la llama al iniciar sesión con el dispositivo que envía el cliente.
    @app.post("/api/v1/sessions/devices/check")
    @solo_servicios("auth")
    def revisar_dispositivo():
        datos = diccionario(leer_cuerpo())
        usuario = entero_positivo(datos.get("usuario"), "usuario")
        identificador = datos.get("dispositivo_id")
        if not isinstance(identificador, str) or not 8 <= len(identificador.strip()) <= 128:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "dispositivo_id debe tener de 8 a 128 caracteres.")
        etiqueta = datos.get("etiqueta")
        etiqueta = etiqueta.strip()[:80] if isinstance(etiqueta, str) and etiqueta.strip() else None
        contexto = Contexto(usuario, request.remote_addr,
                            (request.headers.get("User-Agent") or "")[:255])
        ficha = dispositivos.registrar(contexto, usuario, identificador.strip(), etiqueta)
        return responder(ficha, "dispositivo")

    @app.get("/api/v1/sessions/devices")
    @requiere_token()
    def listar_dispositivos():
        usuario = request.args.get("user_id")
        dueno = g.contexto.user_id if usuario is None else entero_positivo(usuario, "user_id")
        if dueno != g.contexto.user_id and ADMIN not in g.usuario["roles"]:
            raise ErrorAPI(403, "PERMISO_INSUFICIENTE",
                           "Solo ADMINISTRADOR ve los dispositivos de otra cuenta.")
        filas = dispositivos.listar(dueno)
        return responder({"total": len(filas), "dispositivos": filas}, "listado")

    @app.post("/api/v1/sessions/devices/<id>/authorize")
    @requiere_token()
    def autorizar_dispositivo(id):
        return _cambiar(id, "autorizado")

    @app.post("/api/v1/sessions/devices/<id>/revoke")
    @requiere_token()
    def revocar_dispositivo(id):
        # Antes del commit: si Redis falla, no queda un dispositivo revocado con sesiones abiertas.
        return _cambiar(id, "revocado", sesiones.cerrar_dispositivo)
