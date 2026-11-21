# Lo técnico que todo servicio necesita de las sesiones: revisar que un token siga vigente.
# Las reglas (abrir, renovar, cerrar, tope de concurrentes) son del servicio `sesiones`.
from . import llaves
from .errores import ErrorAPI
from .http import llamar
from .redis_compartido import requerido
from .seguridad import token_servicio

# El token se acepta un poco después de su exp por la diferencia entre relojes;
# su revocación dura eso de más.
TOLERANCIA = 60


def verificar(sid, jti):
    def operar(r):
        p = r.pipeline(transaction=False)
        p.exists(llaves.revocado(jti))
        p.exists(llaves.sesion(llaves.huella(sid)))
        return p.execute()

    revocado, abierta = requerido("token_verificar", operar)
    if revocado:
        return "revocado"
    return "vigente" if abierta else "sin_sesion"


def cerrar_de_usuario(usuario):
    # Cliente de la ruta interna de `sesiones`; la regla de cerrar es de ese servicio.
    from flask import current_app
    respuesta = llamar("sesiones", "DELETE", "/api/v1/sessions/user/%d" % usuario,
                       token=token_servicio(current_app.config, current_app.name))
    if respuesta.status_code != 200:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "sesiones no pudo cerrar las sesiones.")
    return respuesta.json()["cerradas"]
