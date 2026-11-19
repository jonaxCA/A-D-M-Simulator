"""series_corridas (D28): un documento por día de cada corrida, con los totales del día.

La escribe el simulador y la lee resultados. El resumen de la corrida va a simulation_runs.
"""
from procesamiento.contrato import CAMPOS_SERIE

from . import mongo

COLECCION = "series_corridas"
VERSION_ESQUEMA = 1
# Quien lee acepta solo las versiones de esquema que conoce.
CONOCIDAS = [1]


def documentos(run, motor, resultado):
    corrida = {"run_id": run["id"], "batch_id": run["batch_id"], "scenario_id": run["scenario_id"],
               "scenario_version_id": run["scenario_version_id"], "motor": motor,
               "engine_version": resultado["engine_version"], "semilla": run["seed"],
               "version_esquema": VERSION_ESQUEMA}
    return [dict(corrida, **{c: fila[c] for c in CAMPOS_SERIE}) for fila in resultado["serie"]]


def guardar(docs):
    # Reemplaza por {run_id, dia}: un reintento de la misma corrida actualiza, no duplica.
    coleccion = mongo.coleccion(COLECCION)
    for d in docs:
        coleccion.replace_one({"run_id": d["run_id"], "dia": d["dia"]}, d, upsert=True)
    return len(docs)


def borrar(run_id):
    return mongo.coleccion(COLECCION).delete_many({"run_id": run_id}).deleted_count


def leer(run_id):
    campos = dict(dict.fromkeys(CAMPOS_SERIE, 1), _id=0)
    cursor = mongo.coleccion(COLECCION).find(
        {"run_id": run_id, "version_esquema": {"$in": CONOCIDAS}}, campos)
    return list(cursor.sort("dia", 1))


def banda(scenario_version_id, motor, campo="casos_activos"):
    """p5, mediana y p95 de `campo` por día, entre las corridas de una versión y un motor."""
    tuberia = [
        {"$match": {"scenario_version_id": scenario_version_id, "motor": motor,
                    "version_esquema": {"$in": CONOCIDAS}}},
        {"$group": {"_id": "$dia", "corridas": {"$sum": 1},
                    "p": {"$percentile": {"input": "$" + campo, "p": [0.05, 0.5, 0.95],
                                          "method": "approximate"}}}},
        {"$sort": {"_id": 1}},
    ]
    return [{"dia": f["_id"], "corridas": f["corridas"],
             "p5": f["p"][0], "p50": f["p"][1], "p95": f["p"][2]}
            for f in mongo.coleccion(COLECCION).aggregate(tuberia)]
