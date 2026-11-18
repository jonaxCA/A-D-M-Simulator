"""MongoDB en el compose de pruebas (D28).

La serie diaria de una corrida va a series_corridas y resultados la regresa. Con MongoDB detenido,
la corrida termina igual con su resumen en PostgreSQL, /indicators responde, /curves da 503 y
casos sigue (RNF-C08); al volver MongoDB, el simulador guarda la serie pendiente.
"""
import pytest
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from microservicios.estado_servicios.sondeo import SERVICIOS

from .conftest import espera

DIAS = 91  # horizon_days de crea_escenario (90) más el día 0


@pytest.fixture(scope="module")
def series(entorno):
    cliente = MongoClient(host="127.0.0.1", port=int(entorno["MONGO_PUERTO_LOCAL"]),
                          username="epidemia", password=entorno["MONGO_PASSWORD"],
                          authSource="epidemia", serverSelectionTimeoutMS=5000)
    yield cliente["epidemia"]["series_corridas"]
    cliente.close()


@pytest.fixture(scope="module")
def version(crea_escenario, aprueba):
    escenario, version, _ = crea_escenario("MongoDB")
    aprueba(escenario)
    return version


def dias_guardados(series, run_id):
    # Mientras MongoDB arranca, la consulta falla: cuenta como cero.
    try:
        return series.count_documents({"run_id": run_id})
    except PyMongoError:
        return 0


def resumen_en_postgres(base, run_id):
    conexion = base()
    with conexion.cursor() as cur:
        cur.execute("SELECT resumen, casos_acumulados FROM simulation_runs WHERE id = %s", (run_id,))
        fila = cur.fetchone()
    conexion.close()
    return fila


def test_la_serie_de_una_corrida_va_a_series_corridas(api, analista, base, version, lanza, termina,
                                                     series):
    run_id = lanza(version, 4242)
    assert termina([run_id]) == {run_id: "completado"}
    espera(lambda: dias_guardados(series, run_id) == DIAS, 30,
           "La serie de la corrida %d no llegó a MongoDB." % run_id)
    docs = list(series.find({"run_id": run_id}, {"_id": 0}).sort("dia", 1))
    assert [d["dia"] for d in docs] == list(range(DIAS))
    assert docs[0]["scenario_version_id"] == version and docs[0]["motor"] == "seir-ref"
    assert docs[0]["semilla"] == 4242 and docs[0]["version_esquema"] == 1

    r = api("resultados", "GET", "/api/v1/runs/%d/results" % run_id, analista["access"])
    assert r.status_code == 200
    assert [p["casos_activos"] for p in r.json()["serie"]] == [d["casos_activos"] for d in docs]
    resumen, acumulados = resumen_en_postgres(base, run_id)
    assert resumen == r.json()["resumen"] and acumulados == resumen["casos_acumulados"]


def test_con_mongodb_detenido_la_corrida_termina_con_su_resumen(api, analista, base, compose,
                                                               sesion, version, lanza, termina,
                                                               series):
    capturista = sesion("capturista")
    compose("stop", "mongodb")
    try:
        run_id = lanza(version, 4343)
        assert termina([run_id]) == {run_id: "completado"}
        assert resumen_en_postgres(base, run_id)[0]
        ruta = "/api/v1/runs/%d/" % run_id
        assert api("resultados", "GET", ruta + "indicators", analista["access"]).status_code == 200
        curvas = api("resultados", "GET", ruta + "curves", analista["access"])
        assert curvas.status_code == 503 and curvas.json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
        assert api("casos", "GET", "/api/v1/cases", capturista["access"]).status_code == 200
    finally:
        compose("start", "mongodb")
    # El simulador reintenta cada 30 s.
    espera(lambda: dias_guardados(series, run_id) == DIAS, 120,
           "La serie pendiente de la corrida %d no se guardó al volver MongoDB." % run_id, cada=3)
    espera(lambda: api("resultados", "GET", "/api/v1/runs/%d/curves" % run_id,
                       analista["access"]).status_code == 200, 30,
           "resultados no regresó la serie al volver MongoDB.")
    espera(lambda: api("estado-servicios", "GET", "/api/v1/services/health").json()["resumen"]["ok"]
           == len(SERVICIOS), 90, "El panel no volvió a ok al volver MongoDB.", cada=3)
