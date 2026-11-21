from procesamiento.contrato import CAMPOS_SERIE

from epidemia_comun import mongo

COLECCION = "series_corridas"
# Contrato: docs/contratos/series_corridas/. Se leen solo las versiones de esquema conocidas.
CONOCIDAS = [1]


def leer(run_id):
    campos = dict(dict.fromkeys(CAMPOS_SERIE, 1), _id=0)
    cursor = mongo.coleccion(COLECCION).find(
        {"run_id": run_id, "version_esquema": {"$in": CONOCIDAS}}, campos)
    return list(cursor.sort("dia", 1))


def con_serie(scenario_version_id, motor, run_ids):
    # De las completadas según PostgreSQL, las que sí tienen su serie en MongoDB.
    filtro = {"scenario_version_id": scenario_version_id, "motor": motor,
              "version_esquema": {"$in": CONOCIDAS}, "run_id": {"$in": list(run_ids)}}
    return sorted(mongo.coleccion(COLECCION).distinct("run_id", filtro))


def banda(scenario_version_id, motor, campo="casos_activos", run_ids=None):
    # run_ids: solo esas corridas, las completadas según PostgreSQL (D38).
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
