from procesamiento.contrato import CAMPOS_SERIE

from epidemia_comun import mongo

COLECCION = "series_corridas"
# Contrato: docs/contratos/series_corridas/. Quien lee acepta solo las versiones que conoce.
VERSION_ESQUEMA = 1


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


def con_serie(run_ids):
    return set(mongo.coleccion(COLECCION).distinct("run_id", {"run_id": {"$in": list(run_ids)}}))
