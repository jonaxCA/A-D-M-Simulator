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
    # Reemplaza la serie de cada corrida: borra lo que haya de su run_id y la inserta completa
    # (D38), así que un reintento no duplica días. Son dos idas y vueltas a MongoDB, no una por
    # día: importa cuando el simulador está lejos, como el de abm-gpu en una PC (D23). Se
    # insertan copias porque insert_many agrega _id a cada documento.
    if not docs:
        return 0
    coleccion = mongo.coleccion(COLECCION)
    for run_id in sorted({d["run_id"] for d in docs}):
        coleccion.delete_many({"run_id": run_id})
    coleccion.insert_many([dict(d) for d in docs], ordered=True)
    return len(docs)


def borrar(run_id):
    return mongo.coleccion(COLECCION).delete_many({"run_id": run_id}).deleted_count


def leer(run_id):
    campos = dict(dict.fromkeys(CAMPOS_SERIE, 1), _id=0)
    cursor = mongo.coleccion(COLECCION).find(
        {"run_id": run_id, "version_esquema": {"$in": CONOCIDAS}}, campos)
    return list(cursor.sort("dia", 1))


def banda(scenario_version_id, motor, campo="casos_activos", run_ids=None):
    """p5, mediana y p95 de `campo` por día, entre las corridas de una versión y un motor.
    `run_ids`: solo esas corridas, las completadas según PostgreSQL (D38)."""
    filtro = {"scenario_version_id": scenario_version_id, "motor": motor,
              "version_esquema": {"$in": CONOCIDAS}}
    if run_ids is not None:
        filtro["run_id"] = {"$in": list(run_ids)}
    tuberia = [
        {"$match": filtro},
        {"$group": {"_id": "$dia", "corridas": {"$sum": 1},
                    "p": {"$percentile": {"input": "$" + campo, "p": [0.05, 0.5, 0.95],
                                          "method": "approximate"}}}},
        {"$sort": {"_id": 1}},
    ]
    return [{"dia": f["_id"], "corridas": f["corridas"],
             "p5": f["p"][0], "p50": f["p"][1], "p95": f["p"][2]}
            for f in mongo.coleccion(COLECCION).aggregate(tuberia)]
