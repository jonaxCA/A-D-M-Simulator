from procesamiento.contrato import CAMPOS_SERIE
from microservicios.resultados import serie


def _guarda(base, run_id, version=11, motor="seir-ref", esquema=1, filas=3):
    base["series_corridas"].insert_many([
        dict(dict.fromkeys(CAMPOS_SERIE, 0), dia=d, casos_activos=d + run_id, run_id=run_id,
             scenario_version_id=version, motor=motor, version_esquema=esquema)
        for d in range(filas)])


def test_leer_regresa_solo_los_campos_de_la_serie_en_orden_de_dia(mongo_falso):
    _guarda(mongo_falso, 1)
    _guarda(mongo_falso, 2)
    filas = serie.leer(1)
    assert [f["dia"] for f in filas] == [0, 1, 2]
    assert set(filas[0]) == set(CAMPOS_SERIE) and filas[1]["casos_activos"] == 2
    assert serie.leer(99) == []


def test_leer_ignora_versiones_de_esquema_desconocidas(mongo_falso):
    _guarda(mongo_falso, 1, esquema=2)
    assert serie.leer(1) == []
