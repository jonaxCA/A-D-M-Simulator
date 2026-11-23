# Las llaves de la tabla del catálogo (docs/arquitectura/microservicios.md). Una
# llave nueva se agrega aquí y en esa tabla; una prueba revisa que coincidan.
import hashlib


# De menor a mayor prioridad (D44); no es una llave, la prueba del catálogo no la toma como tal.
prioridades = ("baja", "normal", "alta")


def cola_simulaciones(motor):
    return f"queue:simulaciones:{motor}"


def cola_con_prioridad(motor, prioridad):
    if prioridad == "normal":
        return cola_simulaciones(motor)
    return f"queue:simulaciones:{motor}:{prioridad}"


# Una sola cola: solo se calibra seir-ref (D50). Como las de corridas, sin TTL.
def cola_calibraciones():
    return "queue:calibraciones"


def avance_calibracion(calibracion):
    return f"calibration:{calibracion}:progress"


def huella(valor):
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def sesion(h):
    return f"session:{h}"


def sesiones_usuario(usuario):
    return f"user:{usuario}:sessions"


def refresh(h):
    return f"refresh:{h}"


def refresh_usado(h):
    return f"refresh:usado:{h}"


def revocado(jti):
    return f"jwt:revoked:{jti}"


def captcha(captcha_id):
    return f"captcha:{captcha_id}"


def mfa(h):
    return f"mfa:{h}"


def mfa_fallos(usuario):
    return f"mfa:fallos:{usuario}"


def mfa_alta(usuario):
    return f"mfa:alta:{usuario}"


def candado_corrida(version):
    return f"lock:corrida:{version}"


# Un simulador vivo y lo que está corriendo (F7); estado-servicios los cuenta por motor.
def latido(motor, simulador):
    return f"worker:{motor}:{simulador}"


def progreso(corrida):
    return f"job:{corrida}:progress"


def cache(servicio, clave):
    return f"cache:{servicio}:{clave}"


def lote(lote_id):
    return f"sync:lote:{lote_id}"


def candado_lote(lote_id):
    return f"sync:lote:{lote_id}:candado"


def salud(servicio):
    return f"health:{servicio}"


# Lo último que estado-servicios avisó de un servicio a los ADMINISTRADOR (F7).
def alerta(servicio):
    return f"alert:{servicio}"


def limite(quien, ruta):
    return f"ratelimit:{quien}:{ruta}"


def errores(servicio):
    return f"errors:{servicio}"
