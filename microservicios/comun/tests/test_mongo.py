import time

import pytest

from epidemia_comun import mongo


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
