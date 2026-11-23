"""La sesión de la web con auth y sesiones (D36): sin leer Redis ni la base.

El access y el refresh viajan en cookies httponly; el nombre de la cuenta, en la sesión firmada
de Flask. La validez la decide `sesiones` en cada petición: sin `sesiones` (o sin Redis detrás)
no se entra, igual que en los servicios.
"""
import os

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


def pide_dispositivo():
    """auth exige dispositivo_id con el MFA prendido o con DISPOSITIVO_OBLIGATORIO=1 (D40, D41). La
    web lo manda solo entonces: con un dispositivo nuevo cualquier cuenta quedaría pendiente.
    Se configuran igual que en auth."""
    return bool((os.environ.get("MFA_PERFILES") or "").strip()) or \
        os.environ.get("DISPOSITIVO_OBLIGATORIO") == "1"


def iniciar(usuario, password, captcha_id, captcha_respuesta, dispositivo=None):
    """La respuesta de auth: los tokens y el usuario, o {"mfa_requerido": True, "mfa_token", ...}
    si su perfil pide segundo factor. Levanta ErrorServicio o ServicioNoDisponible."""
    cuerpo = {"usuario": usuario, "password": password, "captcha_id": captcha_id,
              "captcha_respuesta": captcha_respuesta}
    if dispositivo and pide_dispositivo():
        cuerpo.update(dispositivo_id=dispositivo, dispositivo_etiqueta="Navegador web")
    datos = llamar("auth", "POST", "/api/v1/auth/login", cuerpo=cuerpo)
    if not datos.get("mfa_requerido"):
        guarda_cuenta(datos)
    return datos


def guarda_cuenta(datos):
    u = datos["usuario"]
    session["cuenta"] = {"username": u["username"], "full_name": u["full_name"]}
    session.pop("permisos", None)
    session.pop("mfa", None)


def mfa(accion, mfa_token, **campos):
    """El segundo paso en auth: verify, enroll o confirm (D40). verify y confirm abren la sesión."""
    datos = llamar("auth", "POST", "/api/v1/auth/mfa/%s" % accion,
                   cuerpo=dict({"mfa_token": mfa_token}, **campos))
    if accion in ("verify", "confirm"):
        guarda_cuenta(datos)
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
    session.pop("permisos", None)
