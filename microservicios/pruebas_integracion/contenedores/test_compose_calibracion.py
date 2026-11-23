"""calibracion de punta a punta (D50): un EPIDEMIOLOGO lanza una calibración corta contra la serie
de D50, calibracion-trabajador la corre y el ajuste queda en la base; la CAPTURISTA no lanza ni
consulta. Una que se detiene a la mitad, con el trabajador detenido, se reencola al arrancar y
termina una sola vez (D38). Otra se cancela en espera."""
import pytest

from microservicios.pruebas_integracion.contenedores.conftest import espera

CORTA = {"samples": 200, "seeds": 1, "quantile": 0.05}


def _conjunto(api, cuenta):
    lista = api("importacion", "GET", "/api/v1/datasets", cuenta["access"], params={"region": "19"}).json()
    return next(c["id"] for c in lista["conjuntos"] if c["code"] == "COVID19_NL_2020_SINTOMAS")


def _lanza(api, cuenta, conjunto, **cambios):
    return api("calibracion", "POST", "/api/v1/calibrations", cuenta["access"],
               json=dict(CORTA, dataset_id=conjunto, **cambios))


def _estado(api, cuenta, cal_id):
    return api("calibracion", "GET", "/api/v1/calibrations/%d" % cal_id, cuenta["access"]).json()


def test_una_calibracion_de_principio_a_fin(api, sesion, base):
    epidemiologo, karla = sesion("epidemiologo"), sesion("capturista")
    conjunto = _conjunto(api, epidemiologo)
    assert _lanza(api, karla, conjunto).status_code == 403
    r = _lanza(api, epidemiologo, conjunto)
    assert r.status_code == 202, r.text
    cal_id = r.json()["id"]
    fila = espera(lambda: (lambda f: f if f["terminal"] else None)(_estado(api, epidemiologo, cal_id)), 120,
                  "La calibración no terminó")
    assert fila["status"] == "completado", fila
    assert fila["perdida"]["aceptadas"] == 10
    ajuste = api("calibracion", "GET", "/api/v1/calibrations/%d/fit" % cal_id, epidemiologo["access"]).json()
    assert len(ajuste["semanas"]) == 22
    assert ajuste["ventanas"]["validacion"]["semanas"] == 7
    escenario = api("calibracion", "GET", "/api/v1/calibrations/%d/scenario" % cal_id, epidemiologo["access"])
    assert escenario.json()["param_overrides"]["r0"]["supuesto"] is False
    xml = api("calibracion", "GET", "/api/v1/calibrations/%d/fit" % cal_id, epidemiologo["access"], formato="xml")
    assert xml.text.startswith("<?xml") and "<semana>" in xml.text
    assert api("calibracion", "GET", "/api/v1/calibrations", karla["access"]).status_code == 403
    with base() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit_log WHERE entity_type = 'calibration' AND entity_id = %s",
                    (str(cal_id),))
        assert cur.fetchone()[0] >= 3


def test_el_trabajador_detenido_reencola_al_volver(api, sesion, compose):
    analista = sesion("analista")
    conjunto = _conjunto(api, analista)
    cal_id = _lanza(api, analista, conjunto, samples=2000, quantile=0.01).json()["id"]
    espera(lambda: _estado(api, analista, cal_id)["status"] == "ejecutando", 60, "No empezó")
    compose("kill", "calibracion-trabajador")
    assert _estado(api, analista, cal_id)["status"] == "ejecutando"
    try:
        compose("up", "-d", "--wait", "calibracion-trabajador")
        fila = espera(lambda: (lambda f: f if f["terminal"] else None)(_estado(api, analista, cal_id)), 180,
                      "La calibración no terminó después de reiniciar el trabajador")
    finally:
        compose("up", "-d", "--wait", "calibracion-trabajador")
    assert (fila["status"], fila["attempts"]) == ("completado", 2)


def test_cancelar_en_espera(api, sesion, compose):
    analista = sesion("analista")
    conjunto = _conjunto(api, analista)
    compose("stop", "calibracion-trabajador")
    try:
        cal_id = _lanza(api, analista, conjunto).json()["id"]
        r = api("calibracion", "POST", "/api/v1/calibrations/%d/cancel" % cal_id, analista["access"])
        assert r.status_code == 200 and r.json()["status"] == "cancelado"
        assert api("calibracion", "POST", "/api/v1/calibrations/%d/cancel" % cal_id,
                   analista["access"]).status_code == 409
    finally:
        compose("up", "-d", "--wait", "calibracion-trabajador")
    assert _estado(api, analista, cal_id)["status"] == "cancelado"


@pytest.mark.parametrize("ruta", ["/api/v1/calibrations/state", "/api/v1/calibrations"])
def test_el_administrador_consulta(api, ruta, sesion):
    assert api("calibracion", "GET", ruta, sesion("admin")["access"]).status_code == 200
