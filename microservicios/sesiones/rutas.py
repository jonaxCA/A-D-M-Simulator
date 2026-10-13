import time
import uuid

import jwt
from flask import current_app, g

from epidemia_comun import sesiones
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.redis_compartido import RedisNoDisponible
from epidemia_comun.seguridad import requiere_token, solo_servicios
from epidemia_comun.validaciones import diccionario, entero_positivo
from backend_web.audit import log_audit

ACCESS_TTL = 20 * 60


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
    @solo_servicios
    def cerrar_de_usuario(id):
        usuario = entero_positivo(id)
        return responder({"usuario": usuario, "cerradas": sesiones.cerrar_todas(usuario)},
                         "sesiones_cerradas")
