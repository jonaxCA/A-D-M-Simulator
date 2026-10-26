"""Lecturas de PostgreSQL de escenarios-xml (solo SELECT; este servicio no escribe tablas)."""
from backend_web.db import query


def leer_escenario(scenario_id, version_number=None):
    """Escenario, una versión (la vigente si no se pide una) y sus intervenciones.

    Regresa None si el escenario o la versión pedida no existen. Las referencias a
    enfermedad, región y tipo de intervención salen como códigos estables.
    """
    escenario = query(
        """SELECT s.id, s.name, s.description,
                  d.code AS disease_code, d.name AS disease_name,
                  g.code AS region_code, g.name AS region_name
           FROM scenarios s
           JOIN diseases d ON d.id = s.disease_id
           JOIN regions  g ON g.id = s.region_id
           WHERE s.id = %s""", (scenario_id,), one=True)
    if not escenario:
        return None
    filtro = "v.version_number = %s" if version_number is not None else "v.is_current"
    params = (scenario_id, version_number) if version_number is not None else (scenario_id,)
    version = query(
        """SELECT v.id, v.version_number, v.status, v.is_current, v.population_size,
                  v.horizon_days, v.initial_infected, v.notes, v.population_by_age,
                  v.population_age_unknown, v.age_unknown_policy
           FROM scenario_versions v
           WHERE v.scenario_id = %s AND """ + filtro, params, one=True)
    if not version:
        return None
    intervenciones = query(
        """SELECT i.id, i.order_index, i.start_day, i.end_day, i.coverage, i.compliance,
                  i.params, t.code AS type_code, g.code AS region_code
           FROM scenario_interventions i
           JOIN intervention_types t ON t.id = i.intervention_type_id
           LEFT JOIN regions g ON g.id = i.target_region_id
           WHERE i.scenario_version_id = %s
           ORDER BY i.order_index, i.start_day, i.id""", (version["id"],))
    return {"escenario": dict(escenario), "version": dict(version),
            "intervenciones": [dict(i) for i in intervenciones]}


def resolver_ids(codigo_enfermedad, codigo_region, codigos_tipos, codigos_regiones):
    """Convierte códigos de catálogo en ids. Regresa (ids, faltantes).

    ids: {"enfermedad": id, "region": id, "tipos": {codigo: id}, "regiones": {codigo: id}}
    faltantes: lista de (ruta, mensaje) de los códigos que no existen.
    """
    ids = {"enfermedad": None, "region": None, "tipos": {}, "regiones": {}}
    faltantes = []
    fila = query("SELECT id FROM diseases WHERE code = %s", (codigo_enfermedad,), one=True)
    if fila:
        ids["enfermedad"] = fila["id"]
    else:
        faltantes.append(("/escenario/enfermedad/@codigo",
                          "No existe la enfermedad con código %s." % codigo_enfermedad))
    regiones = {codigo_region} | set(codigos_regiones)
    filas = query("SELECT id, code FROM regions WHERE code = ANY(%s)", (sorted(regiones),))
    por_codigo = {f["code"]: f["id"] for f in filas}
    if codigo_region in por_codigo:
        ids["region"] = por_codigo[codigo_region]
    else:
        faltantes.append(("/escenario/region/@codigo",
                          "No existe la región con código %s." % codigo_region))
    for codigo in sorted(set(codigos_regiones)):
        if codigo in por_codigo:
            ids["regiones"][codigo] = por_codigo[codigo]
        else:
            faltantes.append(("/escenario/version/intervenciones/intervencion/@region",
                              "No existe la región con código %s." % codigo))
    if codigos_tipos:
        filas = query("SELECT id, code FROM intervention_types WHERE code = ANY(%s)",
                      (sorted(set(codigos_tipos)),))
        ids["tipos"] = {f["code"]: f["id"] for f in filas}
        for codigo in sorted(set(codigos_tipos) - set(ids["tipos"])):
            faltantes.append(("/escenario/version/intervenciones/intervencion/@tipo",
                              "No existe el tipo de intervención %s." % codigo))
    return ids, faltantes
