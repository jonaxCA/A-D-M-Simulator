"""
Dispositivos de las apps: la tabla devices (migraciones 002 y 031).

La escribe solo el microservicio dispositivos: registrar uno, volver a
registrarse desde el mismo (actualiza su version y su ultima conexion) y
revocarlo. casos la lee para no aceptar un caso de un dispositivo ajeno o
revocado. push_token no sale de aqui ni entra a la bitacora: solo se dice si
hay uno.
"""
import re

import psycopg2.errors
import psycopg2.extras

from .audit import log_audit
from .db import get_conn, query

# ck_devices_platform (002).
PLATAFORMAS = ("android", "ios", "desktop")
UID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
# Lo que se puede actualizar al volver a registrarse, con el tamano de su columna.
ACTUALIZABLES = {"model": 80, "app_version": 20, "push_token": 255}
CAMPOS = {"device_uid", "platform", *ACTUALIZABLES}
_COLUMNAS = ("id, user_id, device_uid, platform, model, app_version, is_revoked, last_seen_at, "
             "created_at, push_token IS NOT NULL AS has_push_token")
_BITACORA = ("user_id", "platform", "model", "app_version", "has_push_token", "is_revoked",
             "last_seen_at")


def _texto(valor):
    if isinstance(valor, str):
        return valor.strip() or None
    return valor


def valida_dispositivo(datos):
    """Lista de errores en espanol; vacia si se puede registrar."""
    errores = []
    desconocidos = set(datos) - CAMPOS
    if desconocidos:
        errores.append("Campos no reconocidos: %s." % ", ".join(sorted(desconocidos)))
    uid = _texto(datos.get("device_uid"))
    if not isinstance(uid, str) or not UID.match(uid):
        errores.append("device_uid debe tener de 8 a 128 letras, números o los signos . _ : -.")
    if (_texto(datos.get("platform")) or "android") not in PLATAFORMAS:
        errores.append("platform debe ser uno de: %s." % ", ".join(PLATAFORMAS))
    for campo, maximo in ACTUALIZABLES.items():
        valor = _texto(datos.get(campo))
        if valor is not None and (not isinstance(valor, str) or len(valor) > maximo):
            errores.append("%s debe ser texto de hasta %d caracteres." % (campo, maximo))
    return errores


def _bitacora(fila):
    datos = {k: fila[k] for k in _BITACORA}
    if datos["last_seen_at"] is not None:
        datos["last_seen_at"] = datos["last_seen_at"].isoformat()
    return datos


def registrar_dispositivo(user_id, datos, *, contexto):
    """Registra el dispositivo de quien inicio sesion, o, si ya era suyo, actualiza
    lo que mande de ACTUALIZABLES y su ultima conexion. platform solo cuenta al
    registrarlo. Recibe datos que ya pasaron valida_dispositivo.

    Devuelve (dispositivo, creado, conflicto): conflicto explica por que no se
    registro (de otra cuenta, revocado o registrandose en otra peticion)."""
    datos = {k: _texto(v) for k, v in datos.items()}
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT {_COLUMNAS} FROM devices WHERE device_uid = %s FOR UPDATE",
                        (datos["device_uid"],))
            previo = cur.fetchone()
            if previo is None:
                try:
                    cur.execute(
                        f"""INSERT INTO devices (user_id, device_uid, platform, model, app_version,
                                                 push_token, last_seen_at)
                            VALUES (%s, %s, %s, %s, %s, %s, now())
                            RETURNING {_COLUMNAS}""",
                        (user_id, datos["device_uid"], datos.get("platform") or "android",
                         datos.get("model"), datos.get("app_version"), datos.get("push_token")))
                except psycopg2.errors.UniqueViolation:
                    return None, False, ("Ese dispositivo se está registrando en otra petición; "
                                         "intenta de nuevo.")
                fila = cur.fetchone()
                log_audit(contexto, "CREATE", "devices", fila["id"], data_after=_bitacora(fila),
                          cur=cur)
            elif previo["user_id"] != user_id:
                return None, False, "Ese dispositivo está registrado en otra cuenta."
            elif previo["is_revoked"]:
                return None, False, ("Este dispositivo está revocado. Para volver a usar la app en "
                                     "él, regístralo con un identificador nuevo.")
            else:
                cambios = {k: datos[k] for k in ACTUALIZABLES if k in datos}
                asignaciones = "".join(f"{k} = %s, " for k in cambios) + "last_seen_at = now()"
                cur.execute(f"UPDATE devices SET {asignaciones} WHERE id = %s RETURNING {_COLUMNAS}",
                            (*cambios.values(), previo["id"]))
                fila = cur.fetchone()
                log_audit(contexto, "UPDATE", "devices", fila["id"], data_before=_bitacora(previo),
                          data_after=_bitacora(fila), cur=cur)
        conn.commit()
    return dict(fila), previo is None, None


def listar_dispositivos(user_id=None, limite=50):
    """Los de una persona, o los de todas con user_id None (para ADMINISTRADOR), del
    mas reciente al mas viejo."""
    filtro, params = ("WHERE user_id = %s", [user_id]) if user_id is not None else ("", [])
    return [dict(f) for f in query(
        f"SELECT {_COLUMNAS} FROM devices {filtro} ORDER BY created_at DESC, id DESC LIMIT %s",
        (*params, limite))]


def get_dispositivo(device_id):
    fila = query(f"SELECT {_COLUMNAS} FROM devices WHERE id = %s", (device_id,), one=True)
    return dict(fila) if fila else None


def revocar_dispositivo(device_id, *, contexto, user_id=None):
    """Revoca un dispositivo para siempre. Con user_id, solo si es de esa persona
    (ADMINISTRADOR pasa None y revoca cualquiera).

    Devuelve (dispositivo, error): "No existe" si no esta o no es suyo, "ya estaba"
    si ya se habia revocado."""
    dueno = "" if user_id is None else "AND user_id = %s"
    params = (device_id,) if user_id is None else (device_id, user_id)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""UPDATE devices SET is_revoked = TRUE
                            WHERE id = %s {dueno} AND NOT is_revoked
                            RETURNING {_COLUMNAS}""", params)
            fila = cur.fetchone()
            if fila is None:
                cur.execute(f"SELECT is_revoked FROM devices WHERE id = %s {dueno}", params)
                actual = cur.fetchone()
                return None, ("No existe el dispositivo." if actual is None
                              else "El dispositivo ya estaba revocado.")
            log_audit(contexto, "UPDATE", "devices", device_id, data_before={"is_revoked": False},
                      data_after={"is_revoked": True}, cur=cur)
        conn.commit()
    return dict(fila), None


def estado_para_captura(device_id, user_id):
    """Si casos puede aceptar un caso de ese dispositivo para esa persona: "ok",
    "ajeno" (no existe o es de otra cuenta) o "revocado"."""
    fila = query("SELECT user_id, is_revoked FROM devices WHERE id = %s", (device_id,), one=True)
    if fila is None or fila["user_id"] != user_id:
        return "ajeno"
    return "revocado" if fila["is_revoked"] else "ok"
