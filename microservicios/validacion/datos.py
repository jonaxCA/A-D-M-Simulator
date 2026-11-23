# Lo que validacion lee para revisar un escenario (E8). escenario_detalle es copia de solo lectura
# del de escenarios, su dueño: test_copias_de_lectura.py revisa que sigan iguales.
from epidemia_comun.bd import query
from procesamiento.entrada_motor import estado_parametros

ESTADO_NL = "19"


def regiones_para_escenario():
    # Nuevo León y sus municipios, con su reparto censal por edad; `sin_edad` es la gente que el
    # censo cuenta sin edad y que no cae en ningún grupo.
    return [dict(f) for f in query(
        """SELECT r.id, r.code, r.name, r.level, r.population,
                  jsonb_object_agg(g.age_group, g.population)
                      FILTER (WHERE g.lower_bound IS NOT NULL) AS grupos,
                  COALESCE(max(g.population) FILTER (WHERE g.lower_bound IS NULL), 0) AS sin_edad
           FROM regions r
           LEFT JOIN region_age_groups g ON g.region_id = r.id
           WHERE r.code = %s OR r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
           GROUP BY r.id, r.code, r.name, r.level, r.population
           ORDER BY (r.level = 'estado') DESC, r.name""", (ESTADO_NL, ESTADO_NL))]


def enfermedades_para_escenario():
    # Las activas, marcadas si no son simulables: ocultarlas dejaría sin entender por qué «falta».
    salida = []
    for d in query("SELECT id, code, name, default_params FROM diseases WHERE is_active ORDER BY name"):
        estado = estado_parametros(d["default_params"])
        salida.append({"id": d["id"], "code": d["code"], "name": d["name"],
                       "simulable": estado["simulable"], "faltan": len(estado["faltan"]),
                       "sin_fuente": len(estado["sin_fuente"]), "supuestos": len(estado["supuestos"])})
    return salida


def parametros_de(disease_id):
    return query("SELECT default_params FROM diseases WHERE id = %s", (disease_id,), one=True)["default_params"]


def version_simulacion(version_id):
    return query(
        """SELECT sv.id, sv.scenario_id, sv.version_number, sv.status
           FROM scenario_versions sv WHERE sv.id = %s""", (version_id,), one=True)


def escenario_detalle(scenario_id, version_number=None):
    escenario = query(
        """SELECT s.id, s.name, s.description, s.status, s.owner_id, s.created_at,
                  d.id AS disease_id, d.name AS enfermedad, d.default_params,
                  g.id AS region_id, g.name AS region, g.population AS region_poblacion,
                  u.full_name AS autor
           FROM scenarios s
           JOIN diseases d ON d.id = s.disease_id
           JOIN regions  g ON g.id = s.region_id
           JOIN users    u ON u.id = s.owner_id
           WHERE s.id = %s""", (scenario_id,), one=True)
    if not escenario:
        return None
    filtro = "v.version_number = %s" if version_number is not None else "v.is_current"
    params = (scenario_id, version_number) if version_number is not None else (scenario_id,)
    version = query(
        """SELECT v.id, v.version_number, v.status, v.is_current, v.population_size,
                  v.horizon_days, v.initial_infected, v.notes, v.created_at,
                  v.population_by_age, v.population_age_unknown, v.age_unknown_policy,
                  v.created_by, v.submitted_at, v.reviewed_at, v.review_comment,
                  v.param_overrides, v.disease_params,
                  u.full_name AS autor, r.full_name AS revisor
           FROM scenario_versions v
           JOIN users u ON u.id = v.created_by
           LEFT JOIN users r ON r.id = v.reviewed_by
           WHERE v.scenario_id = %s AND """ + filtro, params, one=True)
    if version_number is not None and version is None:
        return None
    intervenciones = []
    if version:
        intervenciones = [dict(r) for r in query(
            """SELECT i.id, i.start_day, i.end_day, i.coverage, i.compliance, i.params,
                      i.order_index, t.code, t.name, t.target_layer, t.param_schema
               FROM scenario_interventions i
               JOIN intervention_types t ON t.id = i.intervention_type_id
               WHERE i.scenario_version_id = %s
               ORDER BY i.order_index, i.start_day, i.id""", (version["id"],))]
    # Un borrador usa el catálogo vivo con los ajustes de la versión encima (044, D59); una versión
    # enviada, su fotografía (D5). Sin fotografía fuera de borrador, la pantalla lo advierte.
    congelada = version["disease_params"] if version else None
    return {
        "escenario": dict(escenario),
        "version": dict(version) if version else None,
        "intervenciones": intervenciones,
        "parametros_enfermedad": congelada or {**(escenario["default_params"] or {}),
                                               **((version or {}).get("param_overrides") or {})},
        "parametros_congelados": congelada is not None,
        "parametros_sin_congelar": bool(version and version["status"] != "borrador" and congelada is None),
        "editable": bool(version and version["is_current"] and version["status"] == "borrador"),
    }
