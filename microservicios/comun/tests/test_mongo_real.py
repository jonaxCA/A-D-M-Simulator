"""Demostración de MongoDB contra un servidor real (D28, RNF-K03, RNF-K14): inserción, consulta
por run_id, actualización, borrado, agregación (la banda p5–p95 por día de una versión y un
motor) e índices. mongomock no tiene $percentile ni explain(), por eso estas van aparte.

Se saltan sin MONGO_URL_PRUEBAS, que apunta a la base epidemia_pruebas del compose. El comando
para correrlas está en «MongoDB» de comun/README.md.
Borran sus colecciones al empezar y al terminar; se niegan a correr sobre la base epidemia.
"""
import os

import pytest
from pymongo.errors import DuplicateKeyError

from epidemia_comun import mongo, series_corridas

URL = os.environ.get("MONGO_URL_PRUEBAS")
pytestmark = pytest.mark.skipif(not URL, reason="Sin MONGO_URL_PRUEBAS")
COLECCIONES = ("series_corridas", "historial_servicios")
FILA = {"S": 990, "E": 0, "I": 10, "R": 0, "H": 0, "D": 0, "V": 0, "casos_activos": 10,
        "nuevos_casos": 0, "nuevas_hospitalizaciones": 0, "nuevas_defunciones": 0,
        "dosis_aplicadas": 0}


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setenv("MONGO_URL", URL)
    mongo.usar(None)
    bd = mongo.base()
    if bd.name == "epidemia":
        pytest.skip("MONGO_URL_PRUEBAS apunta a la base de la demostración")
    for nombre in COLECCIONES:
        bd.drop_collection(nombre)
    yield bd
    for nombre in COLECCIONES:
        bd.drop_collection(nombre)
    mongo.usar(None)


def corrida(run_id, version=11, escala=1, dias=5):
    serie = [dict(FILA, dia=d, casos_activos=(d + 1) * escala) for d in range(dias)]
    run = {"id": run_id, "batch_id": run_id, "scenario_id": 3, "scenario_version_id": version,
           "seed": run_id}
    return series_corridas.documentos(run, "seir-ref", {"engine_version": "seir-ref-0.1",
                                                         "serie": serie})


def test_insercion_consulta_y_actualizacion(base):
    assert series_corridas.guardar(corrida(1)) == 5
    assert [f["casos_activos"] for f in series_corridas.leer(1)] == [1, 2, 3, 4, 5]
    # Volver a guardar la misma corrida reemplaza sus días: no los duplica.
    series_corridas.guardar(corrida(1, escala=10))
    assert base["series_corridas"].count_documents({"run_id": 1}) == 5
    assert [f["casos_activos"] for f in series_corridas.leer(1)] == [10, 20, 30, 40, 50]
    assert base["series_corridas"].find_one({"run_id": 1})["scenario_id"] == 3
    assert series_corridas.borrar(1) == 5 and series_corridas.leer(1) == []


def test_el_indice_unico_no_deja_repetir_un_dia(base):
    series_corridas.guardar(corrida(2))
    with pytest.raises(DuplicateKeyError):
        base["series_corridas"].insert_one(corrida(2)[0])


def test_la_banda_p5_p95_por_dia_de_una_version_y_un_motor(base):
    for run_id in range(1, 21):
        series_corridas.guardar(corrida(run_id, escala=run_id))
    series_corridas.guardar(corrida(99, version=12, escala=1000))
    banda = series_corridas.banda(11, "seir-ref")
    assert [b["dia"] for b in banda] == [0, 1, 2, 3, 4]
    assert all(b["corridas"] == 20 for b in banda)
    # El día 0 vale 1, 2, …, 20 en las veinte corridas de la versión 11.
    dia0 = banda[0]
    assert 1 <= dia0["p5"] <= 2 and 10 <= dia0["p50"] <= 11 and 19 <= dia0["p95"] <= 20
    assert series_corridas.banda(12, "seir-ref")[0]["corridas"] == 1
    assert series_corridas.banda(11, "abm-ref") == []


def test_las_consultas_usan_sus_indices(base):
    series_corridas.guardar(corrida(3))
    por_corrida = base["series_corridas"].find({"run_id": 3}).sort("dia", 1).explain()
    assert "run_id_1_dia_1" in str(por_corrida["queryPlanner"]["winningPlan"])
    por_version = base["series_corridas"].find(
        {"scenario_version_id": 11, "motor": "seir-ref"}).explain()
    assert "scenario_version_id_1_motor_1_dia_1" in str(por_version["queryPlanner"]["winningPlan"])


def test_el_historial_vence_a_los_30_dias(base):
    mongo.coleccion("historial_servicios")
    indices = base["historial_servicios"].index_information().values()
    assert any(i.get("expireAfterSeconds") == 30 * 86400 for i in indices)
