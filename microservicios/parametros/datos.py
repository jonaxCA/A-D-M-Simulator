# Los parámetros de una enfermedad (diseases.default_params) y su historial de versiones
# (disease_parameter_versions, 042, D58). Cada cambio es una versión completa, guardada en la misma
# transacción que el cambio y su bitácora; nada se edita ni se borra (D52).
import psycopg2.extras

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import a_jsonb, get_conn, query
from epidemia_comun.errores import ErrorAPI


def parametros(disease_id):
    fila = query("SELECT default_params FROM diseases WHERE id = %s", (disease_id,), one=True)
    return None if fila is None else (fila["default_params"] or {})


def guardar(disease_id, combinar, motivo, *, contexto):
    """combinar(anteriores) regresa los parámetros nuevos ya validados. Regresa (parámetros, versión)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT default_params FROM diseases WHERE id = %s FOR UPDATE", (disease_id,))
            fila = cur.fetchone()
            if fila is None:
                raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
            anteriores = fila["default_params"] or {}
            nuevos = combinar(anteriores)
            cur.execute("UPDATE diseases SET default_params = %s::jsonb WHERE id = %s",
                        (a_jsonb(nuevos), disease_id))
            cur.execute(
                """INSERT INTO disease_parameter_versions (disease_id, version, params, reason, changed_by)
                   SELECT %s, coalesce(max(version), 0) + 1, %s::jsonb, %s, %s
                     FROM disease_parameter_versions WHERE disease_id = %s
                   RETURNING version""",
                (disease_id, a_jsonb(nuevos), motivo, contexto.user_id, disease_id))
            version = cur.fetchone()["version"]
            log_audit(contexto, "UPDATE", "diseases", disease_id,
                      data_before={"default_params": anteriores},
                      data_after={"default_params": nuevos, "version_parametros": version,
                                  "motivo": motivo}, cur=cur)
        conn.commit()
    return nuevos, version


def versiones(disease_id):
    return [dict(f) for f in query(
        """SELECT version, reason, changed_by, created_at FROM disease_parameter_versions
           WHERE disease_id = %s ORDER BY version DESC""", (disease_id,))]


def version(disease_id, numero):
    fila = query("""SELECT version, params, reason, changed_by, created_at FROM disease_parameter_versions
                    WHERE disease_id = %s AND version = %s""", (disease_id, numero), one=True)
    return dict(fila) if fila else None
