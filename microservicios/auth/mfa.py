import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn

PASO = 30
DIGITOS = 6
VENTANA = 1
RESPALDOS = 8
LARGO_RESPALDO = 10
PENDIENTE_MINUTOS = 15


def nuevo_secreto():
    return base64.b32encode(secrets.token_bytes(20)).decode()


def uri(secreto, usuario):
    return "otpauth://totp/EPIDEMIA:%s?secret=%s&issuer=EPIDEMIA&algorithm=SHA1&digits=%d&period=%d" % (
        quote(usuario), secreto, DIGITOS, PASO)


def codigo(secreto, paso):
    resumen = hmac.new(base64.b32decode(secreto), struct.pack(">Q", paso), hashlib.sha1).digest()
    inicio = resumen[-1] & 15
    numero = int.from_bytes(resumen[inicio:inicio + 4], "big") & 0x7FFFFFFF
    return str(numero % 10 ** DIGITOS).zfill(DIGITOS)


def paso_valido(secreto, entrada, ultimo=None, ahora=None):
    actual = int((time.time() if ahora is None else ahora) // PASO)
    for paso in range(actual - VENTANA, actual + VENTANA + 1):
        if (ultimo is None or paso > ultimo) and hmac.compare_digest(codigo(secreto, paso).encode(),
                                                                      entrada.encode()):
            return paso
    return None


def _huella(usuario, respaldo):
    # La sal es la cuenta: un volcado de la tabla no se ataca para todas las cuentas a la vez.
    return hashlib.pbkdf2_hmac("sha256", respaldo.encode(), b"epidemia-mfa-respaldo:%d" % usuario,
                               100_000).hex()


def normalizar_respaldo(texto):
    return texto.replace("-", "").replace(" ", "").lower()


def estado(usuario):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT secret, enabled, last_counter, "
                        "(NOT enabled AND updated_at > now() - make_interval(mins => %s)) "
                        "FROM user_mfa WHERE user_id = %s", (PENDIENTE_MINUTOS, usuario))
            fila = cur.fetchone()
    return None if fila is None else {"secret": fila[0], "enabled": fila[1], "last_counter": fila[2],
                                      "pendiente_reciente": fila[3]}


def guardar_secreto(contexto, usuario, secreto):
    # Un secreto pendiente reciente no se sobrescribe; se reemplaza al vencer o tras restablecer.
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO user_mfa (user_id, secret) VALUES (%s, %s) "
                        "ON CONFLICT (user_id) DO UPDATE SET secret = EXCLUDED.secret "
                        "WHERE NOT user_mfa.enabled "
                        "AND user_mfa.updated_at <= now() - make_interval(mins => %s)",
                        (usuario, secreto, PENDIENTE_MINUTOS))
            guardado = cur.rowcount == 1
            if guardado:
                log_audit(contexto, "UPDATE", "user_mfa", usuario,
                          data_after={"enabled": False, "secreto_nuevo": True}, cur=cur)
        conn.commit()
    return guardado


def confirmar(contexto, usuario, paso):
    codigos = [base64.b32encode(secrets.token_bytes(10)).decode()[:LARGO_RESPALDO].lower()
               for _ in range(RESPALDOS)]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE user_mfa SET enabled = TRUE, enrolled_at = now(), last_counter = %s "
                        "WHERE user_id = %s AND enabled = FALSE", (paso, usuario))
            if cur.rowcount != 1:
                return None
            cur.execute("DELETE FROM mfa_backup_codes WHERE user_id = %s", (usuario,))
            cur.executemany("INSERT INTO mfa_backup_codes (user_id, code_hash) VALUES (%s, %s)",
                            [(usuario, _huella(usuario, c)) for c in codigos])
            log_audit(contexto, "CREATE", "user_mfa", usuario,
                      data_after={"enabled": True, "respaldos": RESPALDOS}, cur=cur)
        conn.commit()
    return ["-".join((c[:5], c[5:])) for c in codigos]


def aceptar_paso(usuario, paso):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE user_mfa SET last_counter = %s WHERE user_id = %s AND enabled "
                        "AND (last_counter IS NULL OR last_counter < %s)", (paso, usuario, paso))
            aceptado = cur.rowcount == 1
        conn.commit()
    return aceptado


def usar_respaldo(contexto, usuario, texto):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE mfa_backup_codes SET used_at = now() WHERE user_id = %s "
                        "AND code_hash = %s AND used_at IS NULL", (usuario, _huella(usuario, texto)))
            usado = cur.rowcount == 1
            if usado:
                cur.execute("SELECT count(*) FROM mfa_backup_codes WHERE user_id = %s "
                            "AND used_at IS NULL", (usuario,))
                log_audit(contexto, "UPDATE", "user_mfa", usuario,
                          data_after={"respaldo_usado": True, "respaldos_restantes": cur.fetchone()[0]},
                          cur=cur)
        conn.commit()
    return usado


def restablecer(contexto, usuario):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mfa_backup_codes WHERE user_id = %s", (usuario,))
            cur.execute("DELETE FROM user_mfa WHERE user_id = %s RETURNING enabled", (usuario,))
            fila = cur.fetchone()
            if fila is not None:
                log_audit(contexto, "DELETE", "user_mfa", usuario,
                          data_before={"enabled": fila[0]}, cur=cur)
        conn.commit()
    return fila is not None
