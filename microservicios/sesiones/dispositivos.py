from epidemia_comun import llaves
from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn
from epidemia_comun.errores import ErrorAPI

COLUMNAS = ("id", "user_id", "label", "status", "authorized_by", "authorized_at",
            "last_seen_at", "created_at")
SELECCION = ", ".join(COLUMNAS)
# Supuesto (D41): tope de dispositivos pendientes por cuenta, para que la contraseña sola no llene la tabla.
MAX_PENDIENTES = 10


def _ficha(fila):
    return {c: (v.isoformat() if hasattr(v, "isoformat") else v) for c, v in zip(COLUMNAS, fila)}


def registrar(contexto, usuario, dispositivo_id, etiqueta):
    h = llaves.huella(dispositivo_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Serializa los registros de una cuenta: "es el primero" y el tope no admiten carreras.
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (usuario,))
            cur.execute("SELECT " + SELECCION + ", device_hash FROM session_devices "
                        "WHERE user_id = %s AND device_hash = %s FOR UPDATE", (usuario, h))
            fila = cur.fetchone()
            if fila is None:
                # El primero nace autorizado: si no, nadie podría autorizarlo.
                cur.execute("SELECT count(*), count(*) FILTER (WHERE status = 'pendiente') "
                            "FROM session_devices WHERE user_id = %s", (usuario,))
                total, pendientes = cur.fetchone()
                if pendientes >= MAX_PENDIENTES:
                    raise ErrorAPI(429, "DEMASIADOS_DISPOSITIVOS",
                                   "La cuenta tiene %d dispositivos pendientes de autorizar." % pendientes)
                primero = total == 0
                cur.execute(
                    "INSERT INTO session_devices (user_id, device_hash, label, status, "
                    "authorized_by, authorized_at, last_seen_at) VALUES (%s, %s, %s, %s, "
                    "%s, CASE WHEN %s THEN now() END, CASE WHEN %s THEN now() END) "
                    "RETURNING " + SELECCION,
                    (usuario, h, etiqueta, "autorizado" if primero else "pendiente",
                     usuario if primero else None, primero, primero))
                ficha = _ficha(cur.fetchone())
                log_audit(contexto, "CREATE", "session_devices", ficha["id"],
                          data_after={"user_id": usuario, "status": ficha["status"]}, cur=cur)
            else:
                ficha = _ficha(fila[:-1])
                if ficha["status"] == "autorizado":
                    cur.execute("UPDATE session_devices SET last_seen_at = now() WHERE id = %s",
                                (ficha["id"],))
        conn.commit()
    return ficha


def autorizado(usuario, huella):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM session_devices WHERE user_id = %s AND device_hash = %s "
                        "AND status = 'autorizado'", (usuario, huella))
            return cur.fetchone() is not None


def listar(usuario):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT " + SELECCION + " FROM session_devices WHERE user_id = %s "
                        "ORDER BY id", (usuario,))
            return [_ficha(f) for f in cur.fetchall()]


def cambiar(contexto, dispositivo, es_admin, estado, antes_de_guardar=None):
    """Regresa (ficha, error). `antes_de_guardar` corre antes del commit, con la fila vieja."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT " + SELECCION + ", device_hash FROM session_devices "
                        "WHERE id = %s FOR UPDATE", (dispositivo,))
            fila = cur.fetchone()
            if fila is None or (fila[1] != contexto.user_id and not es_admin):
                return None, "NO_ENCONTRADO"
            antes = _ficha(fila[:-1])
            if antes["status"] == estado:
                return antes, "SIN_CAMBIO"
            if antes["status"] == "revocado" and not es_admin:
                return None, "SOLO_ADMIN"
            if estado == "autorizado":
                cur.execute("UPDATE session_devices SET status = %s, authorized_by = %s, "
                            "authorized_at = now() WHERE id = %s RETURNING " + SELECCION,
                            (estado, contexto.user_id, dispositivo))
            else:
                cur.execute("UPDATE session_devices SET status = %s WHERE id = %s "
                            "RETURNING " + SELECCION, (estado, dispositivo))
            despues = _ficha(cur.fetchone())
            log_audit(contexto, "UPDATE", "session_devices", dispositivo,
                      data_before=antes, data_after=despues, cur=cur)
            if antes_de_guardar:
                antes_de_guardar(antes["user_id"], fila[-1])
        conn.commit()
    return despues, None
