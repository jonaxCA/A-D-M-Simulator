import logging
import uuid

from epidemia_comun import sesiones
from epidemia_comun.redis_compartido import RedisNoDisponible

from backend_web.auth import TOKEN_TTL_MINUTES, create_token, decode_token

log = logging.getLogger(__name__)

MENSAJE_SIN_REDIS = ("El servicio de sesiones no está disponible por ahora. "
                     "Intenta entrar de nuevo en unos minutos.")


def abre_sesion(user):
    sesion = sesiones.abrir(user["id"], user["roles"], TOKEN_TTL_MINUTES * 60)
    return create_token(user, sid=sesion["sid"], jti=uuid.uuid4().hex)


def sesion_vigente(payload):
    sid, jti = payload.get("sid"), payload.get("jti")
    if not sid or not jti:
        return False
    try:
        return sesiones.verificar(sid, jti) == "vigente"
    except RedisNoDisponible:
        log.warning("Redis no disponible: no se puede verificar la revocación de la sesión %s",
                    user_id(payload))
        return True


def cierra_sesion(token):
    payload = decode_token(token) if token else None
    if not payload or not payload.get("sid") or not payload.get("jti"):
        return
    try:
        sesiones.cerrar(payload["sid"])
        sesiones.revocar(payload["jti"], int(payload["exp"]))
    except RedisNoDisponible:
        log.warning("Redis no disponible: la sesión %s no se pudo revocar", user_id(payload))


def user_id(payload):
    return payload.get("sub")
