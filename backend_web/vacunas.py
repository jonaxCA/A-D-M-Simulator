"""
Lotes de vacuna: la tabla vaccine_lots (migraciones 005 y 033).

La escribe solo el microservicio vacunas. La app movil lee el codigo del lote
por QR o codigo de barras, lo registra una vez y despues le descuenta las dosis
que aplica. Que nunca se apliquen mas dosis de las que trae lo garantizan el
UPDATE condicionado y ck_vaccine_lots_usadas. Un lote caducado se registra, pero
ya no se le aplican dosis. Ligar un caso a su lote (cases.vaccine_lot_id) es de
casos, no de aqui.
"""
import re
from datetime import date

import psycopg2.errors
import psycopg2.extras

from .audit import log_audit
from .db import get_conn, query
from .queries import ZONA_HORARIA

CODIGO = re.compile(r"^[\x21-\x7e]{1,60}$")
FABRICANTE_MAX = 120
DOSIS_MAX = 1_000_000
APLICAR_MAX = 1000
CAMPOS = {"lot_code", "manufacturer", "disease_id", "region_id", "doses_total", "expires_on"}
_HOY = f"(now() AT TIME ZONE '{ZONA_HORARIA}')::date"
_COLUMNAS = f"""l.id, l.lot_code, l.manufacturer, l.disease_id, d.name AS disease_name,
                l.region_id, r.name AS region_name, l.doses_total, l.doses_used,
                l.doses_total - l.doses_used AS doses_remaining, l.expires_on,
                COALESCE(l.expires_on < {_HOY}, FALSE) AS vencido, l.scanned_by, l.scanned_at"""
_DESDE = """FROM vaccine_lots l
            JOIN diseases d ON d.id = l.disease_id
            LEFT JOIN regions r ON r.id = l.region_id"""


def _entero(valor):
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor)
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _texto(valor):
    return valor.strip() or None if isinstance(valor, str) else valor


def valida_lote(datos):
    """(datos limpios, errores en espanol). Los errores vacios: se puede registrar."""
    errores = []
    desconocidos = set(datos) - CAMPOS
    if desconocidos:
        errores.append("Campos no reconocidos: %s." % ", ".join(sorted(desconocidos)))
    limpios = {"lot_code": _texto(datos.get("lot_code")),
               "manufacturer": _texto(datos.get("manufacturer")),
               "disease_id": _entero(datos.get("disease_id")),
               "region_id": None, "doses_total": _entero(datos.get("doses_total")),
               "expires_on": None}
    if not isinstance(limpios["lot_code"], str) or not CODIGO.match(limpios["lot_code"]):
        errores.append("lot_code debe tener de 1 a 60 caracteres visibles, sin espacios.")
    if limpios["manufacturer"] is not None and (not isinstance(limpios["manufacturer"], str)
                                                or len(limpios["manufacturer"]) > FABRICANTE_MAX):
        errores.append("manufacturer debe ser texto de hasta %d caracteres." % FABRICANTE_MAX)
    if limpios["disease_id"] is None or limpios["disease_id"] < 1:
        errores.append("disease_id debe ser el id de una enfermedad.")
    if datos.get("region_id") not in (None, ""):
        limpios["region_id"] = _entero(datos["region_id"])
        if limpios["region_id"] is None or limpios["region_id"] < 1:
            errores.append("region_id debe ser el id de una región.")
    if limpios["doses_total"] is None or not 1 <= limpios["doses_total"] <= DOSIS_MAX:
        errores.append("doses_total debe ser un entero de 1 a %d." % DOSIS_MAX)
    if datos.get("expires_on") not in (None, ""):
        try:
            limpios["expires_on"] = date.fromisoformat(str(datos["expires_on"]).strip())
        except ValueError:
            errores.append("expires_on debe ser una fecha AAAA-MM-DD.")
    return limpios, errores


def _lote(cur, lote_id):
    cur.execute(f"SELECT {_COLUMNAS} {_DESDE} WHERE l.id = %s", (lote_id,))
    return dict(cur.fetchone())


def registrar_lote(datos, user_id, *, contexto):
    """Registra un lote con datos que ya pasaron valida_lote. Si ese codigo ya estaba con
    los mismos datos (un reintento de la app), regresa el que habia.

    Devuelve (lote, creado, conflicto): conflicto explica por que no se registro."""
    campos = ("manufacturer", "disease_id", "region_id", "doses_total", "expires_on")
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT id, {', '.join(campos)} FROM vaccine_lots WHERE lot_code = %s",
                        (datos["lot_code"],))
            previo = cur.fetchone()
            if previo:
                if all(previo[c] == datos[c] for c in campos):
                    return _lote(cur, previo["id"]), False, None
                return None, False, ("El lote %s ya está registrado con otros datos; consúltalo "
                                     "por su código." % datos["lot_code"])
            try:
                cur.execute(
                    """INSERT INTO vaccine_lots (lot_code, manufacturer, disease_id, region_id,
                                                 doses_total, expires_on, scanned_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (datos["lot_code"], *(datos[c] for c in campos), user_id))
            except psycopg2.errors.UniqueViolation:
                return None, False, "Ese lote se está registrando en otra petición; intenta de nuevo."
            except psycopg2.errors.ForeignKeyViolation:
                return None, False, "La enfermedad o la región no existen."
            lote = _lote(cur, cur.fetchone()["id"])
            log_audit(contexto, "CREATE", "vaccine_lots", lote["id"],
                      data_after={"lot_code": lote["lot_code"], "disease_id": lote["disease_id"],
                                  "region_id": lote["region_id"], "doses_total": lote["doses_total"],
                                  "expires_on": datos["expires_on"] and datos["expires_on"].isoformat()},
                      cur=cur)
        conn.commit()
    return lote, True, None


def aplicar_dosis(lote_id, dosis, *, contexto):
    """Descuenta `dosis` del lote si le quedan y no ha caducado.

    Devuelve (lote, error): "No existe" si no esta; si no, por que no se aplicaron."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""UPDATE vaccine_lots SET doses_used = doses_used + %s
                            WHERE id = %s AND doses_used + %s <= doses_total
                              AND (expires_on IS NULL OR expires_on >= {_HOY})
                            RETURNING doses_used""", (dosis, lote_id, dosis))
            fila = cur.fetchone()
            if fila is None:
                cur.execute(f"SELECT {_COLUMNAS} {_DESDE} WHERE l.id = %s", (lote_id,))
                actual = cur.fetchone()
                if actual is None:
                    return None, "No existe el lote."
                if actual["vencido"]:
                    return None, ("El lote caducó el %s: ya no se le aplican dosis."
                                  % actual["expires_on"].isoformat())
                return None, "Al lote le quedan %d dosis." % actual["doses_remaining"]
            log_audit(contexto, "UPDATE", "vaccine_lots", lote_id,
                      data_before={"doses_used": fila["doses_used"] - dosis},
                      data_after={"doses_used": fila["doses_used"]}, cur=cur)
            lote = _lote(cur, lote_id)
        conn.commit()
    return lote, None


def listar_lotes(lot_code=None, disease_id=None, region_id=None, limite=50):
    """Los mas recientes primero."""
    condiciones, params = [], []
    for columna, valor in (("l.lot_code", lot_code), ("l.disease_id", disease_id),
                           ("l.region_id", region_id)):
        if valor is not None:
            condiciones.append(f"{columna} = %s")
            params.append(valor)
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return [dict(f) for f in query(
        f"SELECT {_COLUMNAS} {_DESDE} {where} ORDER BY l.scanned_at DESC, l.id DESC LIMIT %s",
        (*params, limite))]


def get_lote(lote_id):
    fila = query(f"SELECT {_COLUMNAS} {_DESDE} WHERE l.id = %s", (lote_id,), one=True)
    return dict(fila) if fila else None
