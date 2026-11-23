# La ficha de una enfermedad con su clasificación y sus definiciones de caso versionadas
# (case_definitions, 042, D58). Un borrador se edita; al publicarlo pasa a vigente y la vigente
# anterior a retirada, en la misma transacción y con su bitácora. Lo publicado no cambia.
import psycopg2
import psycopg2.extras

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import a_jsonb, get_conn, query
from epidemia_comun.errores import ErrorAPI

FICHA = ("id", "code", "name", "description", "is_active", "created_at", "transmission", "icd10",
         "classification_source")
_DEFINICION = """SELECT version, status, criteria AS criterios, source AS fuente, source_url AS url,
                        created_by, created_at, published_by, published_at, retired_at
                 FROM case_definitions"""


def enfermedad(disease_id):
    fila = query("SELECT %s FROM diseases WHERE id = %%s" % ", ".join(FICHA), (disease_id,), one=True)
    return dict(fila) if fila else None


def definiciones(disease_id):
    return [dict(f) for f in query(_DEFINICION + " WHERE disease_id = %s ORDER BY version DESC", (disease_id,))]


def definicion(disease_id, version=None):
    # La de esa versión, o la vigente si no se da una.
    if version is None:
        fila = query(_DEFINICION + " WHERE disease_id = %s AND status = 'vigente'", (disease_id,), one=True)
    else:
        fila = query(_DEFINICION + " WHERE disease_id = %s AND version = %s", (disease_id, version), one=True)
    return dict(fila) if fila else None


def crea_borrador(disease_id, criterios, fuente, url, *, contexto):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM diseases WHERE id = %s FOR UPDATE", (disease_id,))
            if cur.fetchone() is None:
                raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
            cur.execute("SELECT version FROM case_definitions WHERE disease_id = %s AND status = 'borrador'",
                        (disease_id,))
            abierto = cur.fetchone()
            if abierto:
                raise ErrorAPI(409, "CONFLICTO", "Ya hay un borrador (versión %d): edítalo o publícalo." % abierto[0])
            cur.execute(
                """INSERT INTO case_definitions (disease_id, version, criteria, source, source_url, created_by)
                   SELECT %s, coalesce(max(version), 0) + 1, %s::jsonb, %s, %s, %s
                     FROM case_definitions WHERE disease_id = %s
                   RETURNING version""",
                (disease_id, a_jsonb(criterios), fuente, url, contexto.user_id, disease_id))
            version = cur.fetchone()[0]
            log_audit(contexto, "CREATE", "case_definitions", "%d/%d" % (disease_id, version),
                      data_after={"disease_id": disease_id, "version": version, "status": "borrador",
                                  "fuente": fuente}, cur=cur)
        conn.commit()
    return version


def _bloquea(cur, disease_id, version):
    cur.execute("SELECT status, criteria, source, source_url FROM case_definitions "
                "WHERE disease_id = %s AND version = %s FOR UPDATE", (disease_id, version))
    fila = cur.fetchone()
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe esa versión de la definición de caso.")
    if fila["status"] != "borrador":
        raise ErrorAPI(409, "CONFLICTO", "La versión %d ya está %s: lo publicado no cambia; crea un borrador nuevo."
                       % (version, fila["status"]))
    return fila


def edita_borrador(disease_id, version, criterios, fuente, url, *, contexto):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            antes = _bloquea(cur, disease_id, version)
            cur.execute("""UPDATE case_definitions SET criteria = %s::jsonb, source = %s, source_url = %s
                           WHERE disease_id = %s AND version = %s""",
                        (a_jsonb(criterios), fuente, url, disease_id, version))
            log_audit(contexto, "UPDATE", "case_definitions", "%d/%d" % (disease_id, version),
                      data_before={"criterios": antes["criteria"], "fuente": antes["source"]},
                      data_after={"criterios": criterios, "fuente": fuente}, cur=cur)
        conn.commit()


def publica(disease_id, version, *, contexto):
    # Regresa la versión que quedó retirada, o None.
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _bloquea(cur, disease_id, version)
            cur.execute("""UPDATE case_definitions SET status = 'retirada', retired_at = now()
                           WHERE disease_id = %s AND status = 'vigente' RETURNING version""", (disease_id,))
            retirada = cur.fetchone()
            cur.execute("""UPDATE case_definitions SET status = 'vigente', published_at = now(), published_by = %s
                           WHERE disease_id = %s AND version = %s""", (contexto.user_id, disease_id, version))
            log_audit(contexto, "PUBLISH", "case_definitions", "%d/%d" % (disease_id, version),
                      data_before={"status": "borrador"},
                      data_after={"status": "vigente", "retirada": retirada and retirada["version"]}, cur=cur)
        conn.commit()
    return retirada and retirada["version"]


def clasifica(disease_id, cambios, *, contexto):
    # Cambia nombre, descripción o clasificación (las columnas de `cambios`).
    columnas = sorted(cambios)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT %s FROM diseases WHERE id = %%s FOR UPDATE" % ", ".join(columnas), (disease_id,))
            antes = cur.fetchone()
            if antes is None:
                raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
            try:
                cur.execute("UPDATE diseases SET %s WHERE id = %%s" % ", ".join("%s = %%s" % c for c in columnas),
                            tuple(cambios[c] for c in columnas) + (disease_id,))
            except psycopg2.errors.CheckViolation:
                raise ErrorAPI(422, "DATOS_INVALIDOS", "La clasificación no cumple las reglas de la base.")
            log_audit(contexto, "UPDATE", "diseases", disease_id, data_before=dict(antes),
                      data_after=dict(cambios), cur=cur)
        conn.commit()
