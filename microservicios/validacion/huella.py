# La huella de una versión (D55): la SHA-256 de la entrada canónica del motor, la misma que calcula
# cada corrida (procesamiento.contrato.huella) y guarda en simulation_runs.scenario_checksum. Con
# ella aprobacion firma la versión aprobada. Las consultas son copia de
# simulador/datos.version_para_motor (columnas y orden de las intervenciones): una prueba revisa que
# sigan iguales (duenos_de_reglas.md).
from epidemia_comun.bd import query
from procesamiento.contrato import huella
from procesamiento.entrada_motor import escenario_de_version

VERSION = """
        SELECT sv.id, sv.scenario_id, sv.version_number, sv.status, sv.population_size,
               sv.horizon_days, sv.initial_infected, sv.population_by_age,
               sv.population_age_unknown, sv.age_unknown_policy, sv.disease_params,
               d.default_params
        FROM scenario_versions sv
        JOIN scenarios s ON s.id = sv.scenario_id
        JOIN diseases d ON d.id = s.disease_id
        WHERE sv.id = %s
        """
INTERVENCIONES = """
        SELECT i.start_day, i.end_day, i.coverage, i.compliance, i.params, t.code
        FROM scenario_interventions i
        JOIN intervention_types t ON t.id = i.intervention_type_id
        WHERE i.scenario_version_id = %s
        ORDER BY i.order_index, i.start_day, i.id
        """


def de_version(version_id):
    # None si la versión no existe. Los parámetros son los congelados al enviarla a revisión o, en
    # un borrador, los vivos de la enfermedad: los mismos que usaría el simulador.
    version = query(VERSION, (version_id,), one=True)
    if not version:
        return None
    intervenciones = [dict(r) for r in query(INTERVENCIONES, (version_id,))]
    return huella(escenario_de_version({
        "version": dict(version), "intervenciones": intervenciones,
        "parametros_enfermedad": version["disease_params"] or version["default_params"]}))
