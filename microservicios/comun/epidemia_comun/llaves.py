# Las llaves de la tabla del catálogo (docs/arquitectura/microservicios.md). Una
# llave nueva se agrega aquí y en esa tabla; una prueba revisa que coincidan.
import hashlib

COLA_SIMULACIONES = "queue:simulaciones"


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


def candado_corrida(version):
    return f"lock:corrida:{version}"


def progreso(corrida):
    return f"job:{corrida}:progress"


def cache(servicio, clave):
    return f"cache:{servicio}:{clave}"


def lote(lote_id):
    return f"sync:lote:{lote_id}"


def salud(servicio):
    return f"health:{servicio}"


def historial_salud(servicio):
    return f"health:history:{servicio}"
