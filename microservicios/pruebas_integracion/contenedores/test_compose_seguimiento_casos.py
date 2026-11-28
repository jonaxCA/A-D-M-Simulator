"""D47 en los contenedores, contra PostgreSQL real (migración 057): corregir con If-Match, el 412
cuando otro cambió el caso, descartar con aviso al capturista, el historial y los conflictos de
una corrección sin conexión en la sincronización."""
import uuid


def _caso(api, karla, catalogo):
    r = api("casos", "POST", "/api/v1/cases", karla["access"], json={
        "local_uuid": str(uuid.uuid4()), "disease_id": catalogo["disease_id"],
        "region_id": catalogo["region_id"], "report_date": "2026-10-20", "age": 30, "sex": "F"})
    assert r.status_code == 201, r.text
    return r.json()


def test_corregir_descartar_e_historial(api, sesion, catalogo, base):
    karla, diana = sesion("capturista"), sesion("epidemiologo")
    caso = _caso(api, karla, catalogo)
    url = "/api/v1/cases/%d" % caso["id"]
    r = api("casos", "GET", url, diana["access"])
    assert r.headers["ETag"] == '"1"' and r.json()["version"] == 1

    r = api("casos", "PATCH", url, karla["access"], json={"age": 31, "reason": "Edad mal capturada"},
            headers={"If-Match": '"1"'})
    assert r.status_code == 200, r.text
    assert (r.json()["version"], r.json()["age"], r.headers["ETag"]) == (2, 31, '"2"')

    # La epidemióloga leyó la versión 1: su corrección no pisa la de la capturista.
    r = api("casos", "PATCH", url, diana["access"], json={"age": 40}, headers={"If-Match": '"1"'})
    assert r.status_code == 412 and r.headers["ETag"] == '"2"'
    assert r.json()["codigo"] == "CONFLICTO"
    assert api("casos", "PATCH", url, diana["access"], json={"age": 40}).status_code == 428

    r = api("casos", "POST", url + "/status", diana["access"],
            json={"status": "descartado", "reason": "Prueba de laboratorio negativa"},
            headers={"If-Match": '"2"'})
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["version"], r.json()["updated_by"]) == ("descartado", 3, diana["id"])

    historial = api("casos", "GET", url + "/history", karla["access"]).json()
    assert [(c["version"], c["action"], c["changed_by"]) for c in historial["cambios"]] == [
        (2, "correccion", karla["id"]), (3, "estado", diana["id"])]
    assert historial["cambios"][0]["changes"] == {"age": {"antes": 30, "despues": 31}}

    # La capturista recibe el aviso del rechazo (tipo CASE_REJECTED de la 057).
    avisos = api("notificaciones", "GET", "/api/v1/notifications", karla["access"],
                 params={"limit": 50}).json()["notificaciones"]
    assert any(a["type"] == "CASE_REJECTED" and a["payload"]["case_id"] == caso["id"] for a in avisos)

    # Ya descartado, la capturista no lo corrige.
    r = api("casos", "PATCH", url, karla["access"], json={"age": 32}, headers={"If-Match": '"3"'})
    assert r.status_code == 403

    conexion = base()
    with conexion.cursor() as cur:
        cur.execute("SELECT count(*) FROM case_history WHERE case_id = %s", (caso["id"],))
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT count(*) FROM audit_log WHERE entity_type = 'cases' AND action = 'UPDATE' "
                    "AND entity_id = %s", (str(caso["id"]),))
        assert cur.fetchone()[0] == 2
    conexion.close()


def test_una_correccion_sin_conexion_sobre_un_caso_que_cambio_es_conflicto(api, sesion, catalogo):
    karla, diana = sesion("capturista"), sesion("epidemiologo")
    caso = _caso(api, karla, catalogo)
    url = "/api/v1/cases/%d" % caso["id"]
    # Mientras el teléfono estaba sin red, la epidemióloga corrigió la edad.
    assert api("casos", "PATCH", url, diana["access"], json={"age": 45},
               headers={"If-Match": '"1"'}).status_code == 200

    def lote(version, edad):
        return api("sincronizacion", "POST", "/api/v1/sync/cases", karla["access"], json={
            "batch_id": str(uuid.uuid4()),
            "updates": [{"case_id": caso["id"], "version": version, "changes": {"age": edad},
                         "reason": "Corregido en campo"}]}).json()

    datos = lote(1, 33)
    (hecha,) = datos["actualizaciones"]
    assert (hecha["resultado"], hecha["version"], hecha["caso"]["age"]) == ("conflicto", 2, 45)
    assert api("casos", "GET", url, karla["access"]).json()["age"] == 45  # no se sobrescribió

    # La capturista ve el conflicto, decide mantener su dato y lo manda con la versión nueva.
    (hecha,) = lote(2, 33)["actualizaciones"]
    assert (hecha["resultado"], hecha["version"]) == ("actualizado", 3)
    assert api("casos", "GET", url, karla["access"]).json()["age"] == 33
