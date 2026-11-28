"""evidencias de punta a punta, con el emulador del bucket (D30): la capturista sube la foto de un
caso suyo, otro rol que lee casos la abre con su URL firmada o la descarga, el reintento no la
duplica, una huella que no coincide no entra, quien no captura no sube y ADMINISTRADOR la borra
del registro y del bucket. El reporte de una comparación sube y se abre igual (D35). Con el bucket
detenido, la subida da 503 y el caso se queda (RNF-C19)."""
import hashlib
import os
import uuid

import requests

JPEG = b"\xff\xd8\xff\xe0" + os.urandom(4096)
PDF = b"%PDF-1.7\n" + os.urandom(4096)


def _caso(api, cuenta, catalogo):
    r = api("casos", "POST", "/api/v1/cases", cuenta["access"], json={
        "local_uuid": str(uuid.uuid4()), "disease_id": catalogo["disease_id"],
        "region_id": catalogo["region_id"], "report_date": "2026-10-20"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_la_foto_de_un_caso(api, sesion, catalogo):
    karla, analista, admin = sesion("capturista"), sesion("analista"), sesion("admin")
    ruta = "/api/v1/cases/%d/attachments" % _caso(api, karla, catalogo)

    def sube(cuenta, huella=None):
        cabeceras = {"Content-Type": "image/jpeg"}
        if huella:
            cabeceras["X-Content-SHA256"] = huella
        return api("evidencias", "POST", ruta, cuenta["access"], data=JPEG, headers=cabeceras)

    assert sube(karla, huella=hashlib.sha256(PDF).hexdigest()).status_code == 422
    r = sube(karla, huella=hashlib.sha256(JPEG).hexdigest())
    assert r.status_code == 201, r.text
    evidencia = r.json()
    assert evidencia["sha256"] == hashlib.sha256(JPEG).hexdigest()
    assert (evidencia["size_bytes"], evidencia["privacy"]) == (len(JPEG), "privado")
    # El reintento de la app no la duplica.
    r = sube(karla)
    assert r.status_code == 200 and r.json()["id"] == evidencia["id"]
    assert sube(analista).status_code == 403

    r = api("evidencias", "GET", "/api/v1/attachments/%d/url" % evidencia["id"], analista["access"])
    assert r.status_code == 200, r.text
    assert r.json()["minutes"] == 15 and "X-Goog-Expires=900" in r.json()["url"]
    descarga = requests.get(r.json()["url"], timeout=10)
    assert descarga.status_code == 200 and descarga.content == JPEG

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


def test_el_reporte_de_una_comparacion(api, sesion, base):
    analista, karla, admin = sesion("analista"), sesion("capturista"), sesion("admin")
    conexion = base()
    with conexion.cursor() as cur:
        cur.execute("SELECT id FROM simulation_runs ORDER BY id LIMIT 2")
        corridas = [f[0] for f in cur.fetchall()]
    conexion.close()
    assert corridas, "La base de pruebas no tiene corridas"
    parametros = {"runs": ",".join(map(str, corridas)), "title": "Prueba de integración"}

    def sube(cuenta):
        return api("evidencias", "POST", "/api/v1/reports", cuenta["access"], data=PDF,
                   params=parametros, headers={"Content-Type": "application/pdf"})

    assert sube(karla).status_code == 403
    r = sube(analista)
    assert r.status_code == 201, r.text
    reporte = r.json()
    assert reporte["run_ids"] == corridas and reporte["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert sube(analista).json()["id"] == reporte["id"]

    r = api("evidencias", "GET", "/api/v1/reports/%d/url" % reporte["id"], sesion("epidemiologo")["access"])
    assert r.status_code == 200, r.text
    assert requests.get(r.json()["url"], timeout=10).content == PDF
    r = api("evidencias", "DELETE", "/api/v1/reports/%d" % reporte["id"], admin["access"])
    assert r.status_code == 200, r.text


def test_con_el_bucket_detenido_la_subida_es_503_y_el_caso_se_queda(api, sesion, catalogo, compose):
    karla = sesion("capturista")
    caso = _caso(api, karla, catalogo)
    compose("stop", "bucket")
    try:
        r = api("evidencias", "POST", "/api/v1/cases/%d/attachments" % caso, karla["access"], data=JPEG,
                headers={"Content-Type": "image/jpeg"})
        assert r.status_code == 503 and r.json()["codigo"] == "SERVICIO_NO_DISPONIBLE", r.text
        salud = api("evidencias", "GET", "/health", formato="json")
        assert salud.status_code == 503 and salud.json()["bucket"] is False
        assert api("casos", "GET", "/api/v1/cases/%d" % caso, karla["access"]).status_code == 200
        assert api("evidencias", "GET", "/api/v1/cases/%d/attachments" % caso,
                   karla["access"]).json()["total"] == 0
    finally:
        compose("start", "bucket")
