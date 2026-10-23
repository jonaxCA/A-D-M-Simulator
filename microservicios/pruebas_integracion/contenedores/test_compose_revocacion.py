"""Revocación entre servicios: lo que cierra sesiones lo rechaza otro servicio."""


def test_logout_en_sesiones_y_el_token_rechazado_en_escenarios(api, sesion):
    propia = sesion("analista")
    assert api("escenarios", "GET", "/api/v1/scenarios", propia["access"]).status_code == 200
    assert api("sesiones", "POST", "/api/v1/sessions/logout", propia["access"]).status_code == 200
    r = api("escenarios", "GET", "/api/v1/scenarios", propia["access"])
    assert r.status_code == 401 and r.json()["codigo"] == "TOKEN_REVOCADO"


def test_reusar_un_refresh_cierra_la_sesion_en_todos(api, sesion):
    propia = sesion("analista")
    nueva = api("sesiones", "POST", "/api/v1/sessions/refresh", json={"refresh_token": propia["refresh"]})
    assert nueva.status_code == 200
    reuso = api("sesiones", "POST", "/api/v1/sessions/refresh", json={"refresh_token": propia["refresh"]})
    assert reuso.status_code == 401
    r = api("escenarios", "GET", "/api/v1/scenarios", nueva.json()["access_token"])
    assert r.status_code == 401 and r.json()["codigo"] == "TOKEN_REVOCADO"
