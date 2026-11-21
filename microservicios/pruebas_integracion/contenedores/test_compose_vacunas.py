"""vacunas de punta a punta: la capturista escanea un lote nuevo, lo registra, el reintento no lo
duplica, le aplica dosis hasta agotarlo y la base no deja pasar ni una más; un lote caducado se
registra pero no se le aplican dosis."""
import uuid
from datetime import date, timedelta


def test_un_lote_de_principio_a_fin(api, sesion, catalogo):
    karla, analista = sesion("capturista"), sesion("analista")
    codigo = "PRUEBA-" + uuid.uuid4().hex[:10].upper()
    r = api("vacunas", "GET", "/api/v1/vaccine-lots", karla["access"], params={"lot_code": codigo})
    assert r.status_code == 200 and r.json()["total"] == 0

    lote = {"lot_code": codigo, "disease_id": catalogo["disease_id"], "region_id": catalogo["region_id"],
            "doses_total": 5, "expires_on": (date.today() + timedelta(days=60)).isoformat()}
    r = api("vacunas", "POST", "/api/v1/vaccine-lots", karla["access"], json=lote)
    assert r.status_code == 201, r.text
    registrado = r.json()
    assert (registrado["doses_remaining"], registrado["vencido"]) == (5, False)
    assert api("vacunas", "POST", "/api/v1/vaccine-lots", karla["access"], json=lote).status_code == 200
    assert api("vacunas", "POST", "/api/v1/vaccine-lots", analista["access"], json=lote).status_code == 403

    dosis = "/api/v1/vaccine-lots/%d/doses" % registrado["id"]
    r = api("vacunas", "POST", dosis, karla["access"], json={"doses": 3})
    assert r.status_code == 200 and r.json()["doses_remaining"] == 2, r.text
    r = api("vacunas", "POST", dosis, karla["access"], json={"doses": 3})
    assert r.status_code == 409 and "quedan 2" in r.json()["detail"]
    assert api("vacunas", "POST", dosis, karla["access"], json={"doses": 2}).status_code == 200
    r = api("vacunas", "GET", "/api/v1/vaccine-lots/%d" % registrado["id"], analista["access"])
    assert r.json()["doses_used"] == 5 and r.json()["doses_remaining"] == 0

    caducado = dict(lote, lot_code=codigo + "-V", expires_on=(date.today() - timedelta(days=2)).isoformat())
    r = api("vacunas", "POST", "/api/v1/vaccine-lots", karla["access"], json=caducado)
    assert r.status_code == 201 and r.json()["vencido"] is True
    r = api("vacunas", "POST", "/api/v1/vaccine-lots/%d/doses" % r.json()["id"], karla["access"],
            json={"doses": 1})
    assert r.status_code == 409 and "caducó" in r.json()["detail"]
