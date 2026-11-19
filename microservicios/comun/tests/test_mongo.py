import time

import pytest

from epidemia_comun import mongo, series_corridas
from procesamiento.contrato import CAMPOS_SERIE


def _llaves(coleccion):
    return {tuple(i["key"]): i for i in coleccion.index_information().values()}


def test_crea_los_indices_de_d28(mongo_falso):
    mongo.coleccion("series_corridas")
    mongo.coleccion("historial_servicios")
    series = _llaves(mongo_falso["series_corridas"])
    assert series[(("run_id", 1), ("dia", 1))].get("unique") is True
    assert (("scenario_version_id", 1), ("motor", 1), ("dia", 1)) in series
    historial = _llaves(mongo_falso["historial_servicios"])
    assert (("servicio", 1), ("fecha", -1)) in historial
    assert historial[(("fecha", 1),)]["expireAfterSeconds"] == 30 * 86400


def test_cada_dia_de_la_serie_lleva_sus_referencias_y_se_borra_por_corrida(mongo_falso):
    serie = [dict(dict.fromkeys(CAMPOS_SERIE, 0), dia=d) for d in range(3)]
    for run_id in (42, 43):
        run = {"id": run_id, "batch_id": 8, "scenario_id": 3, "scenario_version_id": 11,
               "seed": 7}
        series_corridas.guardar(series_corridas.documentos(
            run, "seir-ref", {"engine_version": "seir-ref-0.1", "serie": serie}))
    doc = mongo_falso["series_corridas"].find_one({"run_id": 42, "dia": 0}, {"_id": 0})
    assert {c: doc[c] for c in ("run_id", "batch_id", "scenario_id", "scenario_version_id",
                                "motor", "engine_version", "semilla", "version_esquema")} == {
        "run_id": 42, "batch_id": 8, "scenario_id": 3, "scenario_version_id": 11,
        "motor": "seir-ref", "engine_version": "seir-ref-0.1", "semilla": 7, "version_esquema": 1}
    assert series_corridas.borrar(42) == 3
    assert series_corridas.leer(42) == [] and len(series_corridas.leer(43)) == 3


def test_ping(mongo_falso):
    assert mongo.ping() is True


def test_requerido_convierte_la_caida_en_503(apagar_mongo):
    apagar_mongo()
    with pytest.raises(mongo.MongoNoDisponible):
        mongo.requerido("prueba", lambda: mongo.coleccion("series_corridas").find_one())
    assert mongo.MongoNoDisponible.http == 503


def test_opcional_regresa_el_defecto(apagar_mongo):
    apagar_mongo()
    assert mongo.opcional("prueba", lambda: mongo.coleccion("x").find_one(), "nada") == "nada"


def test_sin_mongo_url_no_hay_base(monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    with pytest.raises(mongo.MongoNoDisponible):
        mongo.base()
    assert mongo.opcional("prueba", mongo.ping) is None


def test_el_cliente_real_sin_servidor_falla_rapido(monkeypatch):
    monkeypatch.setenv("MONGO_URL", "mongodb://127.0.0.1:9/epidemia")
    monkeypatch.setenv("MONGO_TIMEOUT_MS", "200")
    try:
        inicio = time.monotonic()
        assert mongo.opcional("prueba", mongo.ping) is None
        assert time.monotonic() - inicio < 3
    finally:
        mongo.usar(None)
