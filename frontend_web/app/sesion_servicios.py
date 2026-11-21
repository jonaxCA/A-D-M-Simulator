"""La sesión de la web con auth y sesiones (D36): sin leer Redis ni la base.

El access y el refresh viajan en cookies httponly; el nombre de la cuenta, en la sesión firmada
de Flask. La validez la decide `sesiones` en cada petición: sin `sesiones` (o sin Redis detrás)
no se entra, igual que en los servicios.
"""
from flask import g, session

from backend_web.servicios import ErrorServicio, ServicioNoDisponible, llamar

COOKIE_ACCESS = "access_token"
COOKIE_REFRESH = "refresh_token"
MENSAJE_SIN_SESIONES = ("El servicio de sesiones no está disponible por ahora. "
                        "Intenta entrar de nuevo en unos minutos.")
MENSAJE_CREDENCIALES = "Usuario, contraseña o captcha incorrectos."


def captcha():
    try:
        return llamar("auth", "GET", "/api/v1/auth/captcha")
    except (ServicioNoDisponible, ErrorServicio):
        return None


def iniciar(usuario, password, captcha_id, captcha_respuesta):
    """La respuesta de auth (tokens y usuario). Levanta ErrorServicio o ServicioNoDisponible."""
    datos = llamar("auth", "POST", "/api/v1/auth/login",
                   cuerpo={"usuario": usuario, "password": password, "captcha_id": captcha_id,
                           "captcha_respuesta": captcha_respuesta})
    u = datos["usuario"]
    session["cuenta"] = {"username": u["username"], "full_name": u["full_name"]}
    return datos


def _actual(token):
    datos = llamar("sesiones", "GET", "/api/v1/sessions/current", token=token)
    cuenta = session.get("cuenta") or {}
    return {"sub": int(datos["usuario"]), "roles": datos["roles"],
            "username": cuenta.get("username"), "full_name": cuenta.get("full_name")}


def usuario(access, refresh):
    """El usuario de la sesión, o None. Si el access venció, lo renueva con el refresh y deja
    los tokens nuevos en g.tokens_nuevos para que la respuesta los guarde."""
    if not access:
        return None
    try:
        return _actual(access)
    except ErrorServicio as exc:
        if exc.estado != 401 or exc.codigo != "TOKEN_EXPIRADO" or not refresh:
            return None
    try:
        nuevos = llamar("sesiones", "POST", "/api/v1/sessions/refresh",
                        cuerpo={"refresh_token": refresh})
        g.tokens_nuevos = (nuevos["access_token"], nuevos["refresh_token"])
        g.access = nuevos["access_token"]
        return _actual(nuevos["access_token"])
    except ErrorServicio:
        return None


def cerrar(access):
    if not access:
        return
    try:
        llamar("sesiones", "POST", "/api/v1/sessions/logout", token=access)
    except (ErrorServicio, ServicioNoDisponible):
        pass
    session.pop("cuenta", None)
