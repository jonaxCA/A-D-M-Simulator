# En Redis solo están las huellas del sid y del refresh: quien lea Redis no puede
# usar lo que encuentre. Cerrar una sesión invalida sus tokens de acceso porque
# verificar() revisa que siga abierta.
import secrets
import time

from . import llaves
from .redis_compartido import requerido, transaccion

# El token se acepta un poco después de su exp por la diferencia entre relojes;
# su revocación dura eso de más.
TOLERANCIA = 60

_REUTILIZADO = object()


class RefreshReutilizado(Exception):
    codigo = "TOKEN_REVOCADO"
    http = 401


def abrir(usuario, roles, ttl):
    sid = secrets.token_urlsafe(32)
    refresh = _nuevo_refresh(sid)
    h, hr = llaves.huella(sid), llaves.huella(refresh)
    ahora = int(time.time())

    def operar(r):
        p = r.pipeline()
        p.hset(llaves.sesion(h), mapping={
            "usuario": usuario,
            "roles": ",".join(roles),
            "creada": ahora,
            "expira": ahora + ttl,
            "refresh": hr,
        })
        p.expire(llaves.sesion(h), ttl)
        p.set(llaves.refresh(hr), h, ex=ttl)
        p.sadd(llaves.sesiones_usuario(usuario), h)
        p.expire(llaves.sesiones_usuario(usuario), ttl)
        p.execute()

    requerido("sesion_abrir", operar)
    return {"sid": sid, "refresh": refresh, "expira": ahora + ttl}


def obtener(sid):
    datos = requerido("sesion_leer", lambda r: r.hgetall(llaves.sesion(llaves.huella(sid))))
    return _sesion(datos) if datos else None


def renovar(refresh):
    sid = refresh.split(".", 1)[0]
    h, hr = llaves.huella(sid), llaves.huella(refresh)
    nuevo = _nuevo_refresh(sid)

    def operar(p):
        if not p.exists(llaves.refresh(hr)):
            return _REUTILIZADO if p.exists(llaves.refresh_usado(hr)) else None
        datos = p.hgetall(llaves.sesion(h))
        ttl = p.ttl(llaves.sesion(h))
        if not datos or ttl < 1:
            return None
        p.multi()
        p.delete(llaves.refresh(hr))
        p.set(llaves.refresh_usado(hr), h, ex=ttl)
        p.set(llaves.refresh(llaves.huella(nuevo)), h, ex=ttl)
        p.hset(llaves.sesion(h), "refresh", llaves.huella(nuevo))
        return datos

    datos = transaccion(
        "refresh_renovar", operar,
        llaves.refresh(hr), llaves.refresh_usado(hr), llaves.sesion(h),
    )
    if datos is _REUTILIZADO:
        # Un refresh ya usado solo puede venir de una copia: se cierra la sesión entera.
        _cerrar(h)
        raise RefreshReutilizado("Ese refresh ya se había usado; la sesión se cerró.")
    if datos is None:
        return None
    return {"sid": sid, "refresh": nuevo, **_sesion(datos)}


def cerrar(sid):
    return _cerrar(llaves.huella(sid))


def cerrar_todas(usuario):
    hs = requerido("sesiones_usuario", lambda r: r.smembers(llaves.sesiones_usuario(usuario)))
    return sum(_cerrar(h) for h in hs)


def revocar(jti, expira):
    ttl = max(1, expira - int(time.time())) + TOLERANCIA
    requerido("token_revocar", lambda r: r.set(llaves.revocado(jti), 1, ex=ttl))


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


def _cerrar(h):
    def operar(p):
        datos = p.hgetall(llaves.sesion(h))
        p.multi()
        p.delete(llaves.sesion(h))
        if datos:
            p.delete(llaves.refresh(datos["refresh"]))
            p.srem(llaves.sesiones_usuario(datos["usuario"]), h)
        return bool(datos)

    return transaccion("sesion_cerrar", operar, llaves.sesion(h))


def _nuevo_refresh(sid):
    # Empieza con el sid: así renovar() sabe de qué sesión es sin guardarlo en Redis.
    return f"{sid}.{secrets.token_urlsafe(32)}"


def _sesion(datos):
    return {
        "usuario": int(datos["usuario"]),
        "roles": datos["roles"].split(",") if datos["roles"] else [],
        "creada": int(datos["creada"]),
        "expira": int(datos["expira"]),
    }
