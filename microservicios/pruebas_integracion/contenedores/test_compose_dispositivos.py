"""dispositivos de punta a punta: la capturista registra su teléfono, captura con él y lo revoca; desde
ese momento casos y sincronizacion rechazan lo que llegue con ese device_id, aunque su token siga
vigente."""
import uuid


def test_un_telefono_revocado_ya_no_captura(api, sesion, catalogo):
    karla, admin = sesion("capturista"), sesion("admin")
    uid = str(uuid.uuid4())
    r = api("dispositivos", "POST", "/api/v1/devices", karla["access"],
            json={"device_uid": uid, "model": "Pixel 7", "app_version": "0.1.0"})
    assert r.status_code == 201, r.text
    telefono = r.json()
    assert telefono["user_id"] == karla["id"] and telefono["is_revoked"] is False
    # Volver a registrarse desde el mismo teléfono no crea otro.
    r = api("dispositivos", "POST", "/api/v1/devices", karla["access"],
            json={"device_uid": uid, "app_version": "0.2.0"})
    assert r.status_code == 200 and r.json()["id"] == telefono["id"]
    assert r.json()["app_version"] == "0.2.0"

    def caso():
        return {"local_uuid": str(uuid.uuid4()), "disease_id": catalogo["disease_id"],
                "region_id": catalogo["region_id"], "report_date": "2026-10-20"}

    r = api("casos", "POST", "/api/v1/cases", karla["access"], json=dict(caso(), device_id=telefono["id"]))
    assert r.status_code == 201, r.text
    assert r.json()["device_id"] == telefono["id"]
    # El teléfono de karla no sirve para capturar con otra cuenta.
    r = api("casos", "POST", "/api/v1/cases", admin["access"], json=dict(caso(), device_id=telefono["id"]))
    assert r.status_code == 422, r.text

    r = api("dispositivos", "POST", "/api/v1/devices/%d/revoke" % telefono["id"], karla["access"])
    assert r.status_code == 200 and r.json()["is_revoked"] is True

    r = api("casos", "POST", "/api/v1/cases", karla["access"], json=dict(caso(), device_id=telefono["id"]))
    assert r.status_code == 409 and r.json()["codigo"] == "CONFLICTO", r.text
    r = api("sincronizacion", "POST", "/api/v1/sync/cases", karla["access"],
            json={"batch_id": str(uuid.uuid4()), "device_id": telefono["id"], "cases": [caso()]})
    assert r.status_code == 200, r.text
    [resultado] = r.json()["resultados"]
    assert resultado["resultado"] == "rechazado" and "revocado" in resultado["errores"][0]
    # Un teléfono revocado no se vuelve a registrar con el mismo identificador.
    r = api("dispositivos", "POST", "/api/v1/devices", karla["access"], json={"device_uid": uid})
    assert r.status_code == 409, r.text
    # ADMINISTRADOR lo ve en la lista de karla.
    r = api("dispositivos", "GET", "/api/v1/devices", admin["access"], params={"user_id": karla["id"]})
    assert telefono["id"] in [d["id"] for d in r.json()["dispositivos"]]
