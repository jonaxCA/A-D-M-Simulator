"""evidencias de punta a punta: la capturista sube la foto de un caso suyo, otro rol que lee casos la
descarga igual, el reintento no la duplica, quien no captura no sube y ADMINISTRADOR la borra del
registro y del volumen."""
import hashlib
import os
import uuid

JPEG = b"\xff\xd8\xff\xe0" + os.urandom(4096)


def test_la_foto_de_un_caso(api, sesion, catalogo):
    karla, analista, admin = sesion("capturista"), sesion("analista"), sesion("admin")
    r = api("casos", "POST", "/api/v1/cases", karla["access"], json={
        "local_uuid": str(uuid.uuid4()), "disease_id": catalogo["disease_id"],
        "region_id": catalogo["region_id"], "report_date": "2026-10-20"})
    assert r.status_code == 201, r.text
    ruta = "/api/v1/cases/%d/attachments" % r.json()["id"]

    def sube(cuenta):
        return api("evidencias", "POST", ruta, cuenta["access"], data=JPEG,
                   headers={"Content-Type": "image/jpeg"})

    r = sube(karla)
    assert r.status_code == 201, r.text
    evidencia = r.json()
    assert evidencia["sha256"] == hashlib.sha256(JPEG).hexdigest()
    assert (evidencia["size_bytes"], evidencia["privacy"]) == (len(JPEG), "privado")
    # El reintento de la app no la duplica.
    r = sube(karla)
    assert r.status_code == 200 and r.json()["id"] == evidencia["id"]
    assert sube(analista).status_code == 403

    contenido = "/api/v1/attachments/%d/content" % evidencia["id"]
    r = api("evidencias", "GET", contenido, analista["access"], formato=None)
    assert r.status_code == 200 and r.content == JPEG
    assert r.headers["Content-Type"] == "image/jpeg"
    assert api("evidencias", "GET", ruta, analista["access"]).json()["total"] == 1

    assert api("evidencias", "DELETE", "/api/v1/attachments/%d" % evidencia["id"],
               karla["access"]).status_code == 403
    r = api("evidencias", "DELETE", "/api/v1/attachments/%d" % evidencia["id"], admin["access"])
    assert r.status_code == 200, r.text
    assert api("evidencias", "GET", contenido, analista["access"], formato=None).status_code == 404
