# Reglas de sesión (D41): abrir, renovar con rotación de refresh, cerrar y limitar las
# concurrentes. En Redis solo están las huellas del sid y del refresh.
import secrets
import time

from epidemia_comun import llaves
from epidemia_comun.redis_compartido import requerido, transaccion
from epidemia_comun.sesiones import TOLERANCIA

_REUTILIZADO = object()


class RefreshReutilizado(Exception):
    codigo = "TOKEN_REVOCADO"
    http = 401


def abrir(usuario, roles, ttl, dispositivo=None, maximo=None):
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
            **({"dispositivo": dispositivo} if dispositivo else {}),
        })
        p.expire(llaves.sesion(h), ttl)
        p.set(llaves.refresh(hr), h, ex=ttl)
        p.sadd(llaves.sesiones_usuario(usuario), h)
        p.expire(llaves.sesiones_usuario(usuario), ttl)
        p.execute()

    requerido("sesion_abrir", operar)
    cerradas = _limitar(usuario, h, maximo) if maximo else 0
    return {"sid": sid, "refresh": refresh, "expira": ahora + ttl, "cerradas": cerradas}


def obtener(sid):
    datos = requerido("sesion_leer", lambda r: r.hgetall(llaves.sesion(llaves.huella(sid))))
    return _sesion(datos) if datos else None


def dispositivo_de(sid):
    return requerido("sesion_dispositivo",
                     lambda r: r.hget(llaves.sesion(llaves.huella(sid)), "dispositivo"))


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


def cerrar_dispositivo(usuario, dispositivo):
    hs = requerido("sesiones_usuario", lambda r: r.smembers(llaves.sesiones_usuario(usuario)))

    def de_ese(r):
        p = r.pipeline()
        for h in hs:
            p.hget(llaves.sesion(h), "dispositivo")
        return p.execute()

    marcas = requerido("sesion_dispositivo", de_ese)
    return sum(_cerrar(h) for h, d in zip(hs, marcas) if d == dispositivo)


def revocar(jti, expira):
    ttl = max(1, expira - int(time.time())) + TOLERANCIA
    requerido("token_revocar", lambda r: r.set(llaves.revocado(jti), 1, ex=ttl))


def _limitar(usuario, nueva, maximo):
    # Pasado el tope se cierra la más antigua; la recién abierta nunca.
    hs = requerido("sesiones_usuario", lambda r: r.smembers(llaves.sesiones_usuario(usuario)))

    def creadas(r):
        p = r.pipeline()
        for h in hs:
            p.hget(llaves.sesion(h), "creada")
        return p.execute()

    vivas = sorted((int(c), h) for h, c in zip(hs, requerido("sesiones_usuario", creadas))
                   if c and h != nueva)
    sobran = len(vivas) + 1 - maximo
    return sum(_cerrar(h) for _, h in vivas[:max(0, sobran)])


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
