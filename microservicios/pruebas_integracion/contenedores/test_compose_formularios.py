"""D48 en los contenedores, contra PostgreSQL real (migración 059): armar y publicar un formulario,
capturar y corregir un caso con sus respuestas, la versión retirada que sigue valiendo y el
formulario obligatorio.

Usa una enfermedad distinta de la del fixture catalogo (INFLUENZA_ESTACIONAL): las demás pruebas
capturan casos de esa sin formulario, y uno obligatorio los rechazaría."""
import uuid

CAMPOS = [
    {"clave": "fiebre_dias", "etiqueta": "Días con fiebre", "tipo": "entero", "obligatorio": True,
     "minimo": 0, "maximo": 30},
    {"clave": "signos_alarma", "etiqueta": "Signos de alarma", "tipo": "opciones",
     "opciones": [{"valor": "vomito", "etiqueta": "Vómito"}, {"valor": "sangrado", "etiqueta": "Sangrado"}]},
]


def test_formularios_de_punta_a_punta(api, sesion, catalogo, base):
    diana, karla = sesion("epidemiologo"), sesion("capturista")
    enfermedades = api("enfermedades", "GET", "/api/v1/diseases").json()["enfermedades"]
    otra = next(e for e in enfermedades if e["code"] != "INFLUENZA_ESTACIONAL")["id"]

    def formulario(**cambios):
        return api("casos", "POST", "/api/v1/forms", diana["access"],
                   json=dict({"disease_id": otra, "title": "Datos clínicos", "fields": CAMPOS}, **cambios))

    def caso(**cambios):
        return api("casos", "POST", "/api/v1/cases", karla["access"], json=dict({
            "local_uuid": str(uuid.uuid4()), "disease_id": otra, "region_id": catalogo["region_id"],
            "report_date": "2026-10-20"}, **cambios))

    r = formulario()
    assert r.status_code == 201, r.text
    v1 = r.json()
    assert (v1["version"], v1["status"]) == (1, "borrador")
    assert formulario().status_code == 409
    assert api("casos", "GET", "/api/v1/forms/%d" % v1["id"], karla["access"]).status_code == 404
    assert api("casos", "POST", "/api/v1/forms/%d/publish" % v1["id"], diana["access"]).status_code == 200
    vigentes = api("casos", "GET", "/api/v1/forms/current", karla["access"], params={"disease_id": otra}).json()
    assert [f["id"] for f in vigentes["formularios"]] == [v1["id"]]

    r = caso(form_id=v1["id"], form_answers={"fiebre_dias": 3, "signos_alarma": ["sangrado"]})
    assert r.status_code == 201, r.text
    capturado = r.json()
    assert capturado["form_answers"] == {"fiebre_dias": 3, "signos_alarma": ["sangrado"]}
    assert caso(form_id=v1["id"], form_answers={"fiebre_dias": 99}).status_code == 422
    assert caso().status_code == 201  # sin formulario, mientras no sea obligatorio

    # Versión 2, obligatoria: la 1 se retira y sigue valiendo; sin formulario ya no se acepta.
    v2 = formulario(required=True).json()
    assert api("casos", "POST", "/api/v1/forms/%d/publish" % v2["id"], diana["access"]).status_code == 200
    r = caso()
    assert r.status_code == 422 and "form_id (%d, versión 2)" % v2["id"] in r.json()["detail"]
    assert caso(form_id=v1["id"], form_answers={"fiebre_dias": 1}).status_code == 201
    estados = {f["version"]: f["status"] for f in api("casos", "GET", "/api/v1/forms", diana["access"],
                                                      params={"disease_id": otra}).json()["formularios"]}
    assert estados == {1: "retirado", 2: "publicado"}

    r = api("casos", "PATCH", "/api/v1/cases/%d" % capturado["id"], karla["access"],
            json={"form_answers": {"fiebre_dias": 4}}, headers={"If-Match": '"1"'})
    assert r.status_code == 200, r.text
    assert (r.json()["version"], r.json()["form_answers"]) == (2, {"fiebre_dias": 4})

    conexion = base()
    with conexion.cursor() as cur:
        cur.execute("SELECT form_id, form_answers FROM cases WHERE id = %s", (capturado["id"],))
        assert cur.fetchone() == (v1["id"], {"fiebre_dias": 4})
        cur.execute("SELECT count(*) FROM audit_log WHERE entity_type = 'case_forms'")
        assert cur.fetchone()[0] >= 4
    conexion.close()

    # Para no dejar un formulario obligatorio en la base de pruebas: una versión 3 que no lo pide.
    v3 = formulario(required=False).json()
    assert api("casos", "POST", "/api/v1/forms/%d/publish" % v3["id"], diana["access"]).status_code == 200
