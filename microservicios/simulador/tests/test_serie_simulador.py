import json
from pathlib import Path

from epidemia_comun import mongo
from microservicios.simulador import serie
from procesamiento.contrato import CAMPOS_SERIE

CONTRATO = Path(__file__).resolve().parents[3] / "docs" / "contratos" / "series_corridas" / "series_corridas.schema.json"


def _docs(run_id, filas=3, escala=1):
    fila = dict.fromkeys(CAMPOS_SERIE, 0)
    run = {"id": run_id, "batch_id": 8, "scenario_id": 3, "scenario_version_id": 11, "seed": 7}
    return serie.documentos(run, "seir-ref", {"engine_version": "seir-ref-0.1", "serie": [
        dict(fila, dia=d, casos_activos=d * escala) for d in range(filas)]})


def test_cada_dia_lleva_sus_referencias_y_se_borra_por_corrida(mongo_falso):
    for run_id in (42, 43):
        serie.guardar(_docs(run_id))
    doc = mongo_falso["series_corridas"].find_one({"run_id": 42, "dia": 0}, {"_id": 0})
    assert {c: doc[c] for c in ("run_id", "batch_id", "scenario_id", "scenario_version_id",
                                "motor", "engine_version", "semilla", "version_esquema")} == {
        "run_id": 42, "batch_id": 8, "scenario_id": 3, "scenario_version_id": 11,
        "motor": "seir-ref", "engine_version": "seir-ref-0.1", "semilla": 7, "version_esquema": 1}
    assert serie.borrar(42) == 3
    assert mongo_falso["series_corridas"].count_documents({"run_id": 42}) == 0
    assert mongo_falso["series_corridas"].count_documents({"run_id": 43}) == 3


def test_guardar_reemplaza_la_serie_con_pocas_idas_y_vueltas(mongo_falso, monkeypatch):
    original = mongo.coleccion
    llamadas = []

    class Contada:
        def __init__(self, coleccion):
            self.coleccion = coleccion

        def __getattr__(self, nombre):
            llamadas.append(nombre)
            return getattr(self.coleccion, nombre)

    monkeypatch.setattr(mongo, "coleccion", lambda nombre: Contada(original(nombre)))
    serie.guardar(_docs(7, 181))
    llamadas.clear()
    docs = _docs(7, 181, escala=10)
    assert serie.guardar(docs) == 181
    assert "_id" not in docs[0]
    assert llamadas == ["delete_many", "insert_many"]
    assert mongo_falso["series_corridas"].count_documents({"run_id": 7}) == 181
    assert mongo_falso["series_corridas"].find_one({"run_id": 7, "dia": 5})["casos_activos"] == 50


def test_los_documentos_cumplen_el_contrato():
    contrato = json.loads(CONTRATO.read_text(encoding="utf-8"))
    for doc in _docs(1):
        assert set(doc) == set(contrato["required"]) == set(contrato["properties"])
    assert contrato["properties"]["version_esquema"]["const"] == serie.VERSION_ESQUEMA
