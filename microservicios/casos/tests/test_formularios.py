"""Formularios por enfermedad, con versiones (D48, F7)."""
import json
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import pytest

from epidemia_comun.errores import ErrorAPI
from microservicios.casos import formularios
# base y bitacora son fixtures de test_casos: importarlas aquí las registra en este módulo.
from microservicios.casos.tests.test_casos import base, bitacora, cuerpo  # noqa: F401

CAMPOS = [
    {"clave": "fiebre_dias", "etiqueta": "Días con fiebre", "tipo": "entero", "obligatorio": True,
     "minimo": 0, "maximo": 30},
    {"clave": "signos_alarma", "etiqueta": "Signos de alarma", "tipo": "opciones",
     "opciones": [{"valor": "dolor_abdominal", "etiqueta": "Dolor abdominal"},
                  {"valor": "vomito", "etiqueta": "Vómito persistente"},
                  {"valor": "sangrado", "etiqueta": "Sangrado de mucosas"}]},
    {"clave": "serotipo", "etiqueta": "Serotipo", "tipo": "opcion",
     "opciones": [{"valor": "den1", "etiqueta": "DEN-1"}, {"valor": "den2", "etiqueta": "DEN-2"}]},
    {"clave": "hospitalizado", "etiqueta": "Hospitalizado", "tipo": "booleano"},
    {"clave": "fecha_toma", "etiqueta": "Fecha de toma", "tipo": "fecha"},
    {"clave": "temperatura", "etiqueta": "Temperatura (°C)", "tipo": "decimal", "minimo": 34, "maximo": 43},
    {"clave": "notas", "etiqueta": "Notas", "tipo": "texto", "max_largo": 20, "ayuda": "Lo que no cabe arriba"},
]


def version(form_id=1, disease_id=1, numero=1, estado="publicado", requerido=False, campos=None):
    return {"id": form_id, "disease_id": disease_id, "version": numero, "status": estado,
            "title": "Dengue", "fields": formularios.definicion({"title": "Dengue", "fields": campos or CAMPOS})["fields"],
            "required": requerido, "created_by": 9, "created_at": datetime(2026, 11, 20, tzinfo=timezone.utc),
            "updated_at": None, "published_by": None if estado == "borrador" else 9,
            "published_at": None if estado == "borrador" else datetime(2026, 11, 21, tzinfo=timezone.utc)}


# ------------------------------------------------------------------ la definición

def test_una_definicion_valida_queda_limpia():
    datos = formularios.definicion({"title": " Dengue ", "fields": CAMPOS, "required": True})
    assert datos["title"] == "Dengue" and datos["required"] is True
    assert [c["clave"] for c in datos["fields"]] == [c["clave"] for c in CAMPOS]
    texto = datos["fields"][-1]
    assert (texto["max_largo"], texto["obligatorio"], texto["ayuda"]) == (20, False, "Lo que no cabe arriba")


@pytest.mark.parametrize("campos,mensaje", [
    ([], "fields"),
    ([dict(CAMPOS[0])] * 2, "repetidas"),
    ([{"clave": "age", "etiqueta": "Edad", "tipo": "entero"}], "campo fijo"),
    ([{"clave": "Fiebre", "etiqueta": "x", "tipo": "entero"}], "minúscula"),
    ([{"clave": "x", "etiqueta": "x", "tipo": "lista"}], "tipo"),
    ([{"clave": "x", "etiqueta": "x", "tipo": "entero", "minimo": 5, "maximo": 1}], "minimo"),
    ([{"clave": "x", "etiqueta": "x", "tipo": "texto", "minimo": 1}], "minimo y maximo"),
    ([{"clave": "x", "etiqueta": "x", "tipo": "texto", "max_largo": 5000}], "max_largo"),
    ([{"clave": "x", "etiqueta": "x", "tipo": "opcion", "opciones": [{"valor": "a", "etiqueta": "A"}]}], "opciones"),
    ([{"clave": "x", "etiqueta": "x", "tipo": "opcion",
       "opciones": [{"valor": "a", "etiqueta": "A"}, {"valor": "a", "etiqueta": "B"}]}], "mismo valor"),
    ([{"clave": "x", "etiqueta": "x", "tipo": "entero", "opciones": []}], "opciones solo"),
    ([{"clave": "x", "etiqueta": "", "tipo": "entero"}], "etiqueta"),
    ([{"clave": "x", "etiqueta": "x", "tipo": "entero", "otro": 1}], "desconocidos"),
    ([{"clave": "x%d" % i, "etiqueta": "x", "tipo": "booleano"} for i in range(61)], "fields"),
])
def test_una_definicion_invalida_es_422(campos, mensaje):
    with pytest.raises(ErrorAPI) as error:
        formularios.definicion({"title": "Dengue", "fields": campos})
    assert error.value.estado == 422 and mensaje in error.value.detalle


def test_title_y_required():
    with pytest.raises(ErrorAPI):
        formularios.definicion({"title": "", "fields": CAMPOS})
    with pytest.raises(ErrorAPI):
        formularios.definicion({"title": "x", "fields": CAMPOS, "required": "si"})


# ------------------------------------------------------------------ las respuestas

def test_respuestas_validas_y_normalizadas():
    limpias = formularios.respuestas(version(), {
        "fiebre_dias": 3, "signos_alarma": ["sangrado", "dolor_abdominal"], "serotipo": "den2",
        "hospitalizado": False, "fecha_toma": "2026-11-20", "temperatura": 38.5, "notas": ""})
    # Las opciones quedan en el orden del formulario; lo vacío no se guarda.
    assert limpias == {"fiebre_dias": 3, "signos_alarma": ["dolor_abdominal", "sangrado"],
                       "serotipo": "den2", "hospitalizado": False, "fecha_toma": "2026-11-20",
                       "temperatura": 38.5}


def test_respuestas_que_llegan_de_un_xml():
    limpias = formularios.respuestas(version(), {
        "fiebre_dias": "4", "signos_alarma": {"item": "vomito"}, "hospitalizado": "true",
        "temperatura": "39.1"})
    assert limpias == {"fiebre_dias": 4, "signos_alarma": ["vomito"], "hospitalizado": True,
                       "temperatura": 39.1}


@pytest.mark.parametrize("crudas,mensaje", [
    ({}, "fiebre_dias es obligatorio"),
    ({"fiebre_dias": 31}, "va de 0 a 30"),
    ({"fiebre_dias": 2.5}, "entero"),
    ({"fiebre_dias": True}, "número"),
    ({"fiebre_dias": 1, "serotipo": "den9"}, "una de"),
    ({"fiebre_dias": 1, "signos_alarma": ["vomito", "vomito"]}, "sin repetir"),
    ({"fiebre_dias": 1, "hospitalizado": "si"}, "true o false"),
    ({"fiebre_dias": 1, "fecha_toma": "20/11/2026"}, "AAAA-MM-DD"),
    ({"fiebre_dias": 1, "temperatura": 50}, "va de 34 a 43"),
    ({"fiebre_dias": 1, "notas": "x" * 21}, "20 caracteres"),
    ({"fiebre_dias": 1, "otro": 1}, "no es un campo"),
    ("texto", "objeto"),
])
def test_respuestas_invalidas_son_422(crudas, mensaje):
    with pytest.raises(ErrorAPI) as error:
        formularios.respuestas(version(), crudas)
    assert error.value.estado == 422 and mensaje in error.value.detalle


def test_todos_los_motivos_juntos():
    with pytest.raises(ErrorAPI) as error:
        formularios.respuestas(version(), {"serotipo": "x", "temperatura": 99})
    detalle = error.value.detalle
    assert "fiebre_dias es obligatorio" in detalle and "serotipo" in detalle and "temperatura" in detalle


def test_la_version_con_que_se_captura():
    assert formularios.para_caso(version(estado="retirado"), 1)["status"] == "retirado"
    for formulario, disease_id, mensaje in ((None, 1, "no es un formulario"), (version(), 2, "otra enfermedad"),
                                            (version(estado="borrador"), 1, "borrador")):
        with pytest.raises(ErrorAPI) as error:
            formularios.para_caso(formulario, disease_id)
        assert mensaje in error.value.detalle


# ------------------------------------------------------------------ las rutas de formularios

class Almacen:
    """case_forms en memoria, con las reglas de la base: un borrador y una publicada por
    enfermedad, versiones consecutivas, y lo publicado no cambia."""

    def __init__(self):
        self.filas = {}

    def lista(self, disease_id=None, estado=None):
        return [dict(f) for f in sorted(self.filas.values(), key=lambda f: (f["disease_id"], f["version"]))
                if (disease_id is None or f["disease_id"] == disease_id) and (estado is None or f["status"] == estado)]

    def crea(self, disease_id, datos, usuario):
        if disease_id != 1:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
        if any(f["disease_id"] == disease_id and f["status"] == "borrador" for f in self.filas.values()):
            raise ErrorAPI(409, "CONFLICTO", "Esa enfermedad ya tiene un borrador.")
        numero = 1 + max([f["version"] for f in self.filas.values() if f["disease_id"] == disease_id], default=0)
        fila = dict(version(len(self.filas) + 1, disease_id, numero, "borrador"), **datos, created_by=int(usuario))
        self.filas[fila["id"]] = fila
        return dict(fila)

    def reemplaza(self, form_id, datos):
        fila = self.filas.get(form_id)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el formulario.")
        if fila["status"] != "borrador":
            raise ErrorAPI(409, "CONFLICTO", "Ya está %s." % fila["status"])
        fila.update(datos)
        return dict(fila)

    def publica(self, form_id, usuario):
        fila = self.filas.get(form_id)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el formulario.")
        if fila["status"] != "borrador":
            raise ErrorAPI(409, "CONFLICTO", "Ya está %s." % fila["status"])
        for otra in self.filas.values():
            if otra["disease_id"] == fila["disease_id"] and otra["status"] == "publicado":
                otra["status"] = "retirado"
        fila.update(status="publicado", published_by=int(usuario), published_at=datetime(2026, 11, 22, tzinfo=timezone.utc))
        return dict(fila)


@pytest.fixture
def almacen(monkeypatch, base):
    a = Almacen()
    monkeypatch.setattr(formularios, "lista", a.lista)
    monkeypatch.setattr(formularios, "vigentes", lambda disease_id=None: a.lista(disease_id, "publicado"))
    monkeypatch.setattr(formularios, "por_id", lambda form_id: dict(a.filas[form_id]) if form_id in a.filas else None)
    monkeypatch.setattr(formularios, "crea_borrador", a.crea)
    monkeypatch.setattr(formularios, "reemplaza_borrador", a.reemplaza)
    monkeypatch.setattr(formularios, "publica", a.publica)
    return a


@pytest.fixture
def cliente(crear_cliente, almacen, bitacora):
    return crear_cliente("casos")


@pytest.fixture
def epi(token):
    return token(roles=("EPIDEMIOLOGO",), sub="9")


@pytest.fixture
def captura(token):
    return token(roles=("CAPTURISTA",))


def nuevo(cliente, cabeceras, **cambios):
    return cliente.post("/api/v1/forms?format=json", headers=cabeceras,
                        json=dict({"disease_id": 1, "title": "Dengue", "fields": CAMPOS}, **cambios))


def test_crear_editar_y_publicar(cliente, epi, captura, bitacora):
    r = nuevo(cliente, epi)
    assert r.status_code == 201
    borrador = r.get_json()
    assert (borrador["version"], borrador["status"], borrador["created_by"]) == (1, "borrador", 9)
    assert nuevo(cliente, epi).status_code == 409  # un borrador a la vez
    r = cliente.put("/api/v1/forms/1?format=json", headers=epi,
                    json={"title": "Dengue v1", "fields": CAMPOS[:2], "required": True})
    assert r.status_code == 200 and r.get_json()["title"] == "Dengue v1"
    # La capturista no ve borradores.
    assert cliente.get("/api/v1/forms/1?format=json", headers=captura).status_code == 404
    assert cliente.get("/api/v1/forms/current?format=json", headers=captura).get_json()["total"] == 0
    r = cliente.post("/api/v1/forms/1/publish?format=json", headers=epi)
    assert r.status_code == 200 and r.get_json()["status"] == "publicado"
    assert cliente.put("/api/v1/forms/1?format=json", headers=epi,
                       json={"title": "x", "fields": CAMPOS}).status_code == 409
    vigentes = cliente.get("/api/v1/forms/current?disease_id=1&format=json", headers=captura).get_json()
    assert [f["version"] for f in vigentes["formularios"]] == [1]
    assert [e[1:3] for e in bitacora] == [("CREATE", "case_forms"), ("UPDATE", "case_forms"), ("UPDATE", "case_forms")]


def test_publicar_otra_version_retira_la_anterior(cliente, epi, captura):
    nuevo(cliente, epi)
    cliente.post("/api/v1/forms/1/publish", headers=epi)
    r = nuevo(cliente, epi, title="Dengue v2")
    assert r.get_json()["version"] == 2
    cliente.post("/api/v1/forms/2/publish", headers=epi)
    datos = cliente.get("/api/v1/forms?disease_id=1&format=json", headers=captura).get_json()
    assert [(f["version"], f["status"]) for f in datos["formularios"]] == [(1, "retirado"), (2, "publicado")]


@pytest.mark.parametrize("roles", [("CAPTURISTA",), ("ANALISTA",)])
def test_solo_epidemiologo_y_administrador_arman_formularios(cliente, token, roles):
    assert nuevo(cliente, token(roles=roles)).status_code == 403


def test_formularios_en_xml(cliente, epi):
    nuevo(cliente, epi)
    raiz = ET.fromstring(cliente.get("/api/v1/forms", headers=epi).data)
    assert raiz.tag == "lista_formularios"
    campo = raiz.find("formularios/formulario/fields/campo")
    assert campo.findtext("clave") == "fiebre_dias"
    opciones = raiz.findall("formularios/formulario/fields/campo")[1].find("opciones").findall("opcion")
    assert [o.findtext("valor") for o in opciones] == ["dolor_abdominal", "vomito", "sangrado"]


@pytest.mark.parametrize("consulta,estado", [("forms/77", 404), ("forms?status=viejo", 422)])
def test_consultas_invalidas(cliente, epi, consulta, estado):
    assert cliente.get("/api/v1/%s&format=json" % consulta if "?" in consulta else "/api/v1/%s?format=json" % consulta,
                       headers=epi).status_code == estado


def test_crear_con_campos_invalidos_o_enfermedad_que_no_existe(cliente, epi):
    assert nuevo(cliente, epi, fields=[]).status_code == 422
    assert nuevo(cliente, epi, disease_id=99).status_code == 404
    assert nuevo(cliente, epi, otro=1).status_code == 422


# ------------------------------------------------------------------ capturar con formulario

@pytest.fixture
def publicado(almacen):
    almacen.filas[1] = version(1, 1, 1, "publicado")
    return almacen


def captura_caso(cliente, cabeceras, **cambios):
    return cliente.post("/api/v1/cases?format=json", headers=cabeceras, json=cuerpo(**cambios))


def test_un_caso_con_su_formulario(cliente, captura, publicado, base):
    r = captura_caso(cliente, captura, form_id=1, form_answers={"fiebre_dias": 3, "signos_alarma": ["vomito"]})
    assert r.status_code == 201, r.get_json()
    datos = r.get_json()
    assert (datos["form_id"], datos["form_answers"]) == (1, {"fiebre_dias": 3, "signos_alarma": ["vomito"]})
    assert base.casos[0]["form_answers"] == {"fiebre_dias": 3, "signos_alarma": ["vomito"]}


def test_respuestas_que_no_pasan_son_422(cliente, captura, publicado):
    r = captura_caso(cliente, captura, form_id=1, form_answers={"fiebre_dias": 99})
    assert r.status_code == 422 and "Formulario (versión 1)" in r.get_json()["detail"]


def test_sin_formulario_se_acepta_mientras_no_sea_obligatorio(cliente, captura, publicado):
    assert captura_caso(cliente, captura).status_code == 201
    publicado.filas[1]["required"] = True
    r = captura_caso(cliente, captura, local_uuid="7a2b3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d")
    assert r.status_code == 422 and "form_id (1, versión 1)" in r.get_json()["detail"]


def test_una_version_retirada_sigue_valiendo(cliente, captura, publicado):
    publicado.filas[1]["status"] = "retirado"
    assert captura_caso(cliente, captura, form_id=1, form_answers={"fiebre_dias": 1}).status_code == 201


@pytest.mark.parametrize("cambios", [
    {"form_answers": {"fiebre_dias": 1}},          # sin form_id
    {"form_id": 9, "form_answers": {}},            # no existe
    {"form_id": "x", "form_answers": {}},          # no es número
])
def test_formulario_mal_referido_es_422(cliente, captura, publicado, cambios):
    assert captura_caso(cliente, captura, **cambios).status_code == 422


def test_un_lote_con_formularios(cliente, captura, publicado):
    casos = [cuerpo(local_uuid="%08d-1111-4111-8111-111111111111" % i, form_id=1,
                    form_answers={"fiebre_dias": i}) for i in (1, 50)]
    datos = cliente.post("/api/v1/cases/batch?format=json", headers=captura, json={"cases": casos}).get_json()
    assert [r["estado"] for r in datos["resultados"]] == [201, 422]


# ------------------------------------------------------------------ corregir las respuestas

def test_corregir_las_respuestas(cliente, captura, publicado, base):
    captura_caso(cliente, captura, form_id=1, form_answers={"fiebre_dias": 3})
    r = cliente.patch("/api/v1/cases/1?format=json", headers=dict(captura, **{"If-Match": '"1"'}),
                      json={"form_answers": {"fiebre_dias": 4, "hospitalizado": True}})
    assert r.status_code == 200, r.get_json()
    assert (r.get_json()["version"], r.get_json()["form_answers"]) == (2, {"fiebre_dias": 4, "hospitalizado": True})
    assert json.loads(base.historial[0]["changes"]) == {
        "form_answers": {"antes": {"fiebre_dias": 3}, "despues": {"fiebre_dias": 4, "hospitalizado": True}}}
    # Respuestas que no pasan: 422 y nada cambia.
    r = cliente.patch("/api/v1/cases/1?format=json", headers=dict(captura, **{"If-Match": '"2"'}),
                      json={"form_answers": {"fiebre_dias": 99}})
    assert r.status_code == 422 and base.casos[0]["version"] == 2


def test_agregar_el_formulario_a_un_caso_que_no_lo_traia(cliente, captura, publicado):
    captura_caso(cliente, captura)
    r = cliente.patch("/api/v1/cases/1?format=json", headers=dict(captura, **{"If-Match": '"1"'}),
                      json={"form_id": 1, "form_answers": {"fiebre_dias": 2}})
    assert r.status_code == 200 and r.get_json()["form_id"] == 1


def test_cambiar_la_enfermedad_pide_el_formulario_nuevo(cliente, captura, publicado, monkeypatch):
    from microservicios.casos import captura as datos_captura
    monkeypatch.setattr(datos_captura, "get_enfermedades_para_captura",
                        lambda: [{"id": 1, "name": "COVID-19"}, {"id": 2, "name": "Dengue"}])
    captura_caso(cliente, captura, form_id=1, form_answers={"fiebre_dias": 3})
    cabeceras = dict(captura, **{"If-Match": '"1"'})
    r = cliente.patch("/api/v1/cases/1?format=json", headers=cabeceras, json={"disease_id": 2})
    assert r.status_code == 422 and "Cambiaste la enfermedad" in r.get_json()["detail"]
    r = cliente.patch("/api/v1/cases/1?format=json", headers=cabeceras, json={"disease_id": 2, "form_id": None})
    assert r.status_code == 200 and (r.get_json()["form_id"], r.get_json()["form_answers"]) == (None, None)
