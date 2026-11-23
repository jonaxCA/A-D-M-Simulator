"""D49 en los contenedores, contra PostgreSQL real (migración 060): campañas con su aviso a los
CAPTURISTA, preferencias que apagan un aviso y el aviso de datos incompletos."""
import uuid
from datetime import date, timedelta


def _avisos(api, cuenta, tipo):
    lista = api("notificaciones", "GET", "/api/v1/notifications", cuenta["access"],
                params={"limit": 200}).json()["notificaciones"]
    return [a for a in lista if a["type"] == tipo]


def test_campanas_preferencias_y_datos_incompletos(api, sesion, catalogo):
    diana, karla, admin = sesion("epidemiologo"), sesion("capturista"), sesion("admin")
    inicio = date.today() + timedelta(days=5)
    campana = {"name": "Vacunación de prueba %s" % uuid.uuid4().hex[:6],
               "disease_id": catalogo["disease_id"], "region_id": catalogo["region_id"],
               "starts_on": inicio.isoformat(), "ends_on": (inicio + timedelta(days=10)).isoformat(),
               "target_population": 5000, "description": "Adultos mayores"}

    r = api("vacunas", "POST", "/api/v1/campaigns", diana["access"], json=campana)
    assert r.status_code == 201, r.text
    creada = r.json()
    assert (creada["status"], creada["municipio"]) == ("programada", "Monterrey")
    assert any(a["payload"]["campaign_id"] == creada["id"] for a in _avisos(api, karla, "CAMPAIGN"))
    assert api("vacunas", "POST", "/api/v1/campaigns", karla["access"], json=campana).status_code == 403

    # La capturista apaga los avisos de campaña: la siguiente no le llega.
    r = api("notificaciones", "PUT", "/api/v1/notifications/preferences", karla["access"], json={"CAMPAIGN": False})
    assert r.status_code == 200, r.text
    try:
        otra = api("vacunas", "POST", "/api/v1/campaigns", diana["access"],
                   json=dict(campana, name=campana["name"] + " b", region_id=None)).json()
        assert otra["municipio"] == "Nuevo León"
        assert not any(a["payload"]["campaign_id"] == otra["id"] for a in _avisos(api, karla, "CAMPAIGN"))
    finally:
        api("notificaciones", "PUT", "/api/v1/notifications/preferences", karla["access"], json={"CAMPAIGN": True})

    r = api("vacunas", "POST", "/api/v1/campaigns/%d/cancel" % creada["id"], diana["access"],
            json={"reason": "Prueba de integración"})
    assert r.status_code == 200 and r.json()["status"] == "cancelada"
    assert api("vacunas", "POST", "/api/v1/campaigns/%d/cancel" % creada["id"], diana["access"],
               json={"reason": "otra vez"}).status_code == 409
    vigentes = api("vacunas", "GET", "/api/v1/campaigns", karla["access"], params={"status": "cancelada"}).json()
    assert creada["id"] in [c["id"] for c in vigentes["campanas"]]

    # SYSTEM no se apaga.
    r = api("notificaciones", "PUT", "/api/v1/notifications/preferences", admin["access"], json={"SYSTEM": False})
    assert r.status_code == 422

    # Un caso sin edad ni ubicación: aviso a quien lo capturó y aparece en sus incompletos.
    r = api("casos", "POST", "/api/v1/cases", karla["access"], json={
        "local_uuid": str(uuid.uuid4()), "disease_id": catalogo["disease_id"],
        "region_id": catalogo["region_id"], "report_date": "2026-10-20", "sex": "F",
        "onset_date": "2026-10-18", "test_result": "positivo", "severity": "leve"})
    assert r.status_code == 201, r.text
    caso = r.json()
    assert any(caso["id"] in a["payload"]["case_ids"] for a in _avisos(api, karla, "DATA_INCOMPLETE"))
    incompletos = api("casos", "GET", "/api/v1/cases/incomplete", karla["access"],
                      params={"per_page": 100}).json()
    encontrado = next(c for c in incompletos["casos"] if c["id"] == caso["id"])
    assert encontrado["faltantes"] == ["edad", "ubicación"]
