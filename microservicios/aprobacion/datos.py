# El flujo de revisión de una versión (D55): enviar, aprobar (con su firma), rechazar y devolver
# para cambios. Vivía en backend_web.queries (envia_a_revision, resuelve_revision y
# get_pendientes_revision); ahora es de aprobacion, el dueño de esas columnas de
# scenario_versions (E8). Las reglas de la base siguen mandando: ck_scenario_versions_envio,
# ck_scenario_versions_revision, ck_scenario_versions_no_autoaprobacion y ck_scenario_versions_firma.
import psycopg2
import psycopg2.extras

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn, query
from epidemia_comun.errores import ErrorAPI

# Lo que deja cada decisión en la versión. Devolver la regresa a borrador con el motivo, sin
# revisor ni parámetros congelados: vuelve a ser editable y se congela otra vez al reenviarla.
DECISIONES = {
    "aprobar": ("aprobado", """status = 'aprobado', reviewed_by = %(revisor)s, reviewed_at = now(),
                               review_comment = %(comentario)s, approval_sha256 = %(huella)s"""),
    "rechazar": ("rechazado", """status = 'rechazado', reviewed_by = %(revisor)s, reviewed_at = now(),
                                 review_comment = %(comentario)s"""),
    "devolver": ("borrador", """status = 'borrador', submitted_at = NULL, reviewed_by = NULL,
                                reviewed_at = NULL, disease_params = NULL,
                                review_comment = %(comentario)s"""),
}


def _conflicto(mensaje):
    return ErrorAPI(409, "CONFLICTO", mensaje)


def escenario_y_version(scenario_id):
    # (escenario, version vigente o None); None si el escenario no existe.
    fila = query(
        """SELECT s.id, s.name, s.owner_id, s.status, s.region_id, v.id AS version_id,
                  v.version_number, v.status AS version_status, v.created_by
           FROM scenarios s
           LEFT JOIN scenario_versions v ON v.scenario_id = s.id AND v.is_current
           WHERE s.id = %s""", (scenario_id,), one=True)
    if fila is None:
        return None
    escenario = {k: fila[k] for k in ("id", "name", "owner_id", "status", "region_id")}
    version = None if fila["version_id"] is None else {
        "id": fila["version_id"], "version_number": fila["version_number"],
        "status": fila["version_status"], "created_by": fila["created_by"]}
    return escenario, version


def pendientes():
    # La bandeja: solo versiones vigentes en revisión, la que lleva más esperando primero.
    return [dict(r) for r in query(
        """SELECT s.id AS scenario_id, s.name, v.version_number, v.submitted_at,
                  v.population_size, v.horizon_days, v.created_by,
                  d.name AS enfermedad, g.name AS region, u.full_name AS autor,
                  (SELECT count(*) FROM scenario_interventions i
                   WHERE i.scenario_version_id = v.id) AS n_intervenciones
           FROM scenario_versions v
           JOIN scenarios s ON s.id = v.scenario_id
           JOIN diseases  d ON d.id = s.disease_id
           JOIN regions   g ON g.id = s.region_id
           JOIN users     u ON u.id = v.created_by
           WHERE v.status = 'en_revision' AND v.is_current
           ORDER BY v.submitted_at, s.name""")]


def envia(version_id, *, contexto):
    # Borrador a en_revision. Aquí se congelan los parámetros de la enfermedad: es el único camino
    # de salida de borrador (024). El motor ya lo revisó validacion antes de llegar aquí.
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE scenario_versions v
                   SET status = 'en_revision', submitted_at = now(), disease_params = d.default_params
                   FROM scenarios s
                   JOIN diseases d ON d.id = s.disease_id
                   WHERE v.id = %s AND v.status = 'borrador' AND v.is_current
                     AND s.id = v.scenario_id AND s.status <> 'archivado'
                   RETURNING v.version_number""", (version_id,))
            fila = cur.fetchone()
            if not fila:
                raise _conflicto("Alguien cambió esta versión o su escenario mientras la enviabas. "
                                 "Recarga y vuelve a intentarlo.")
            log_audit(contexto, "UPDATE", "scenario_versions", version_id,
                      data_before={"status": "borrador"},
                      data_after={"status": "en_revision", "version_number": fila[0],
                                  "parametros_congelados": True}, cur=cur)
        conn.commit()


def resuelve(version_id, decision, comentario, *, contexto, huella=None):
    # Devuelve el estado nuevo. Nadie resuelve lo que creó, también al devolver; la base lo vuelve
    # a comprobar al aprobar o rechazar (ck_scenario_versions_no_autoaprobacion).
    estado, asignacion = DECISIONES[decision]
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT created_by, status, version_number FROM scenario_versions "
                            "WHERE id = %s FOR UPDATE", (version_id,))
                version = cur.fetchone()
                if version is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la versión.")
                if version["created_by"] == contexto.user_id:
                    raise _conflicto("No puedes revisar una versión que tú creaste: la revisión la "
                                     "hace otra persona.")
                if version["status"] != "en_revision":
                    raise _conflicto("Alguien resolvió esta revisión mientras la tuya estaba "
                                     "abierta. Recarga la página.")
                cur.execute("UPDATE scenario_versions SET %s WHERE id = %%(id)s AND status = 'en_revision'"
                            % asignacion, {"revisor": contexto.user_id, "comentario": comentario or None,
                                           "huella": huella, "id": version_id})
                despues = {"status": estado, "version_number": version["version_number"],
                           "decision": decision, "review_comment": comentario or None}
                if decision == "aprobar":
                    despues["approval_sha256"] = huella
                log_audit(contexto, "UPDATE", "scenario_versions", version_id,
                          data_before={"status": "en_revision"}, data_after=despues, cur=cur)
            conn.commit()
    except psycopg2.errors.CheckViolation as exc:
        raise _conflicto("La base rechazó la revisión: %s" % exc.diag.message_primary)
    return estado


def firma(version_id):
    # La firma guardada al aprobar y cómo salieron las corridas de esa versión contra ella.
    version = query(
        """SELECT v.id AS version_id, v.scenario_id, v.version_number, v.status, v.approval_sha256,
                  v.reviewed_at, rev.full_name AS revisor
           FROM scenario_versions v
           LEFT JOIN users rev ON rev.id = v.reviewed_by
           WHERE v.id = %s""", (version_id,), one=True)
    if version is None:
        return None
    corridas = query(
        """SELECT count(*) FILTER (WHERE scenario_checksum = %(h)s) AS coinciden,
                  count(*) FILTER (WHERE scenario_checksum IS NOT NULL
                                     AND scenario_checksum IS DISTINCT FROM %(h)s) AS distintas,
                  count(*) FILTER (WHERE scenario_checksum IS NULL) AS sin_huella
           FROM simulation_runs WHERE scenario_version_id = %(v)s""",
        {"h": version["approval_sha256"], "v": version_id}, one=True)
    return dict(version, corridas=dict(corridas))
