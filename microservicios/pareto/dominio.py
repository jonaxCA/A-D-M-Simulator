from procesamiento.analitica import ComparacionInvalida, comparar
from procesamiento.entrada_motor import entrada_de_version

from . import datos


def id_simulacion(run_id):
    return f"SIM-{int(run_id):05d}"


def construir_escenario_desde_version(version_id):
    version, intervenciones = datos.version_para_motor(version_id)
    return entrada_de_version(version, intervenciones)


def construir_comparacion_costo_impacto(run_ids, metrica="fallecimientos"):
    if len(run_ids) < 2:
        return None, ["Selecciona al menos dos corridas completadas."]

    # Pesos por tipo y, para los tipos por dosis, personas-día por dosis (D3).
    costos, factores = {}, {}
    for tipo in datos.get_tipos_intervencion():
        if tipo["unit_cost"] is not None:
            costos[tipo["code"]] = {
                "valor": float(tipo["unit_cost"]),
                "fuente": tipo["cost_source"],
                "supuesto": bool(tipo["cost_is_assumption"]),
            }
        if tipo.get("person_days_per_unit") is not None:
            factores[tipo["code"]] = {
                "valor": float(tipo["person_days_per_unit"]),
                "fuente": tipo["person_days_source"],
                "supuesto": bool(tipo["person_days_is_assumption"]),
            }

    entradas = []
    errores = []

    for run_id in run_ids:
        run = datos.get_run(run_id)
        if not run or run["status"] != "completado":
            errores.append(f"La corrida {id_simulacion(run_id)} no esta completada.")
            continue

        escenario, _version, errores_escenario = construir_escenario_desde_version(
            run["scenario_version_id"]
        )
        if errores_escenario:
            errores.extend(f"{id_simulacion(run_id)}: {e}" for e in errores_escenario)
            continue

        guardado = datos.get_resultado_run(run_id)
        if not guardado:
            errores.append(f"{id_simulacion(run_id)} no tiene resultados guardados.")
            continue

        resultado = {
            "huella_escenario": guardado["scenario_checksum"],
            "resumen": guardado["resumen"],
            "semilla": run["seed"],
            "engine_version": guardado["engine_version"],
            "dias": run["horizon_days"],
            "poblacion": run["population_size"],
        }

        entradas.append({
            "id": run_id,
            "nombre": f"{id_simulacion(run_id)} - {run['scenario_name']}",
            "escenario": escenario,
            "resultado": resultado,
        })

    if errores:
        return None, errores

    try:
        return comparar(entradas, costos, metrica=metrica, factores=factores), []
    except ComparacionInvalida as exc:
        return None, exc.errores
