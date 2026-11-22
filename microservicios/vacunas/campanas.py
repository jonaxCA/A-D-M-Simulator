"""Campañas de salud (D49, F7): de una enfermedad, en un municipio de Nuevo León o en todo el
estado, con sus fechas, la población objetivo y la descripción.

Las crean, editan y cancelan el EPIDEMIOLOGO y el ADMINISTRADOR; las consultan los cuatro roles.
Al crear o cancelar una, los CAPTURISTA reciben un aviso CAMPAIGN (rutas.py). El estado sale de
las fechas: programada, activa, terminada, o cancelada si se canceló. Sin coberturas: eso es el
servicio opcional de vacunación.
"""
from datetime import date

import psycopg2.extras

from epidemia_comun.bd import get_conn, query
from epidemia_comun.errores import ErrorAPI

ESTADOS = ("programada", "activa", "terminada", "cancelada")
POBLACION_MAXIMA = 20000000
_ESTADO = """CASE WHEN c.cancelled_at IS NOT NULL THEN 'cancelada'
                  WHEN current_date < c.starts_on THEN 'programada'
                  WHEN current_date > c.ends_on THEN 'terminada'
                  ELSE 'activa' END"""
_SELECT = """SELECT c.id, c.name, c.disease_id, d.name AS enfermedad, c.region_id,
                    coalesce(r.name, 'Nuevo León') AS municipio, c.starts_on, c.ends_on,
                    c.target_population, c.description, {estado} AS status, c.created_by,
                    c.created_at, c.updated_at, c.cancelled_at, c.cancelled_by, c.cancel_reason
             FROM campaigns c
             JOIN diseases d ON d.id = c.disease_id
             LEFT JOIN regions r ON r.id = c.region_id""".format(estado=_ESTADO)


# ------------------------------------------------------------------ validación

def _texto(valor, campo, maximo, obligatorio):
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obligatorio:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "%s es obligatorio." % campo)
        return None
    if not isinstance(valor, str):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s es texto." % campo)
    if len(valor.strip()) > maximo:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s no puede pasar de %d caracteres." % (campo, maximo))
    return valor.strip()


def _entero(valor, campo, obligatorio, maximo=2 ** 31 - 1):
    if valor is None or valor == "":
        if obligatorio:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "%s es obligatorio." % campo)
        return None
    texto = str(valor).strip() if isinstance(valor, (int, str)) and not isinstance(valor, bool) else ""
    if not texto.isdigit() or not 1 <= int(texto) <= maximo:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s es un entero de 1 a %d." % (campo, maximo))
    return int(texto)


def _fecha(valor, campo):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s es una fecha AAAA-MM-DD." % campo)


def datos(cuerpo, hoy=None):
    """Los campos de una campaña, limpios, de un alta o una edición (se manda todo)."""
    if not isinstance(cuerpo, dict):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "La campaña es un objeto.")
    desconocidos = set(cuerpo) - {"name", "disease_id", "region_id", "starts_on", "ends_on",
                                  "target_population", "description"}
    if desconocidos:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Campos no reconocidos: " + ", ".join(sorted(str(c) for c in desconocidos)) + ".")
    limpios = {"name": _texto(cuerpo.get("name"), "name", 160, True),
               "disease_id": _entero(cuerpo.get("disease_id"), "disease_id", True, 32767),
               "region_id": _entero(cuerpo.get("region_id"), "region_id", False),
               "starts_on": _fecha(cuerpo.get("starts_on"), "starts_on"),
               "ends_on": _fecha(cuerpo.get("ends_on"), "ends_on"),
               "target_population": _entero(cuerpo.get("target_population"), "target_population",
                                            False, POBLACION_MAXIMA),
               "description": _texto(cuerpo.get("description"), "description", 2000, False)}
    if limpios["ends_on"] < limpios["starts_on"]:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "ends_on no puede ser anterior a starts_on.")
    if limpios["ends_on"] < (hoy or date.today()):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "La campaña ya terminó: ends_on es anterior a hoy.")
    return limpios


def motivo(cuerpo):
    if not isinstance(cuerpo, dict) or set(cuerpo) - {"reason"}:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Solo se acepta reason.")
    return _texto(cuerpo.get("reason"), "reason", 500, True)


# ------------------------------------------------------------------ la base

def verifica_catalogos(disease_id, region_id):
    if query("SELECT id FROM diseases WHERE id = %s", (disease_id,), one=True) is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
    if region_id is not None and query(
            """SELECT id FROM regions WHERE id = %s AND level = 'municipio'
               AND parent_region_id = (SELECT id FROM regions WHERE code = '19')""",
            (region_id,), one=True) is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el municipio en Nuevo León.")


def lista(estado=None, disease_id=None, region_id=None, limite=50):
    condiciones, params = [], []
    if estado is not None:
        condiciones.append(_ESTADO + " = %s")
        params.append(estado)
    if disease_id is not None:
        condiciones.append("c.disease_id = %s")
        params.append(disease_id)
    if region_id is not None:
        # Las de ese municipio y las de todo el estado.
        condiciones.append("(c.region_id = %s OR c.region_id IS NULL)")
        params.append(region_id)
    donde = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return [dict(f) for f in query(_SELECT + donde + " ORDER BY c.starts_on DESC, c.id DESC LIMIT %s",
                                   tuple(params) + (limite,))]


def por_id(campana_id):
    fila = query(_SELECT + " WHERE c.id = %s", (campana_id,), one=True)
    return dict(fila) if fila else None


def crea(limpios, usuario):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""INSERT INTO campaigns (name, disease_id, region_id, starts_on, ends_on,
                                                  target_population, description, created_by)
                           VALUES (%(name)s, %(disease_id)s, %(region_id)s, %(starts_on)s, %(ends_on)s,
                                   %(target_population)s, %(description)s, %(usuario)s)
                           RETURNING id""", dict(limpios, usuario=usuario))
            nuevo = cur.fetchone()["id"]
        conn.commit()
    return por_id(nuevo)


def _editable(campana_id, cur, accion):
    cur.execute("SELECT " + _ESTADO + " AS status FROM campaigns c WHERE c.id = %s FOR UPDATE",
                (campana_id,))
    fila = cur.fetchone()
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la campaña.")
    if fila["status"] in ("cancelada", "terminada"):
        raise ErrorAPI(409, "CONFLICTO", "La campaña ya está %s: no se %s." % (fila["status"], accion))


def actualiza(campana_id, limpios):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _editable(campana_id, cur, "edita")
            cur.execute("""UPDATE campaigns SET name = %(name)s, disease_id = %(disease_id)s,
                                  region_id = %(region_id)s, starts_on = %(starts_on)s,
                                  ends_on = %(ends_on)s, target_population = %(target_population)s,
                                  description = %(description)s, updated_at = now()
                           WHERE id = %(id)s""", dict(limpios, id=campana_id))
        conn.commit()
    return por_id(campana_id)


def cancela(campana_id, razon, usuario):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _editable(campana_id, cur, "cancela")
            cur.execute("""UPDATE campaigns SET cancelled_at = now(), cancelled_by = %s,
                                  cancel_reason = %s, updated_at = now()
                           WHERE id = %s""", (usuario, razon, campana_id))
        conn.commit()
    return por_id(campana_id)
