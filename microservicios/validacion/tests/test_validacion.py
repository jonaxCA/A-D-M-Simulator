import copy

import pytest

from backend_web import queries
from procesamiento.tests.corpus_resolver import ENFERMEDAD

REGIONES = [
    {"id": 1, "code": "19", "name": "Nuevo León", "level": "estado", "population": 5000000,
     "grupos": None, "sin_edad": 0},
    {"id": 2, "code": "19039", "name": "Monterrey", "level": "municipio", "population": 1100000,
     "grupos": {"0-19": 300000, "20-59": 600000, "60+": 200000}, "sin_edad": 0},
]
ENFERMEDADES = [
    {"id": 1, "code": "FLU", "name": "Influenza", "simulable": True, "faltan": 0,
     "sin_fuente": 0, "supuestos": 0},
    {"id": 2, "code": "X", "name": "Incompleta", "simulable": False, "faltan": 2,
     "sin_fuente": 0, "supuestos": 0},
]
TIPOS = [{"id": 1, "code": "CIERRE_ESCUELAS", "name": "Cierre de escuelas",
          "param_schema": {"type": "object", "properties": {}}}]

VALIDO = {"name": "Brote", "disease_id": 1, "region_id": 1, "population_size": 100000,
          "initial_infected": 10, "horizon_days": 60}


@pytest.fixture
def cliente(crear_cliente, monkeypatch):
    monkeypatch.setattr(queries, "get_regiones_para_escenario", lambda: copy.deepcopy(REGIONES))
    monkeypatch.setattr(queries, "get_enfermedades_para_escenario", lambda: copy.deepcopy(ENFERMEDADES))
    monkeypatch.setattr(queries, "get_tipos_intervencion", lambda: copy.deepcopy(TIPOS))
    monkeypatch.setattr(queries, "query",
                        lambda sql, params=(), one=False: {"default_params": copy.deepcopy(ENFERMEDAD)})
    # Nada de escribir: si la ruta intentara guardar, estas pruebas lo notarían.
    for nombre in ("execute", "get_conn", "log_audit"):
        monkeypatch.setattr(queries, nombre, _prohibido, raising=False)
    return crear_cliente("validacion")


def _prohibido(*_a, **_k):
    raise AssertionError("validacion no escribe")


@pytest.fixture
def analista(token):
    return token(roles=("ANALISTA",))


def post(cliente, headers, cuerpo, formato="json"):
    return cliente.post("/api/v1/validate?format=" + formato, json=cuerpo, headers=headers)


def test_escenario_valido(cliente, analista):
    r = post(cliente, analista, VALIDO)
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["valido"] is True and datos["errores"] == []
    assert isinstance(datos["avisos"], list)


def test_no_valido_es_200_con_errores(cliente, analista):
    r = post(cliente, analista, {**VALIDO, "name": "", "initial_infected": 0})
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["valido"] is False
    assert "El nombre del escenario es obligatorio." in datos["errores"]
    assert len(datos["errores"]) >= 2


def test_enfermedad_no_simulable_y_region_inexistente(cliente, analista):
    datos = post(cliente, analista, {**VALIDO, "disease_id": 2, "region_id": 99}).get_json()
    assert datos["valido"] is False
    assert any("no se puede simular" in e for e in datos["errores"])
    assert any("región" in e for e in datos["errores"])


def test_el_motor_rechaza(cliente, analista, monkeypatch):
    monkeypatch.setattr(queries, "query", lambda *a, **k: {"default_params": {}})
    datos = post(cliente, analista, VALIDO).get_json()
    assert datos["valido"] is False
    assert all(e.startswith("El motor rechaza el escenario:") for e in datos["errores"])


def test_estratificar_toma_el_censo(cliente, analista):
    datos = post(cliente, analista, {**VALIDO, "region_id": 2, "estratificar": True}).get_json()
    assert datos["valido"] is True


def test_reparto_por_edad_que_no_cuadra(cliente, analista):
    cuerpo = {**VALIDO, "region_id": 2, "population_by_age": {"0-19": 1, "20-59": 2, "60+": 3}}
    datos = post(cliente, analista, cuerpo).get_json()
    assert datos["valido"] is False and any("censo" in e for e in datos["errores"])
    cuerpo["population_by_age"] = REGIONES[1]["grupos"]
    assert post(cliente, analista, cuerpo).get_json()["valido"] is True


def test_intervenciones(cliente, analista):
    bien = {"code": "CIERRE_ESCUELAS", "start_day": 5, "end_day": 40}
    datos = post(cliente, analista, {**VALIDO, "interventions": [bien]}).get_json()
    assert datos["valido"] is True
    mal = post(cliente, analista, {**VALIDO, "interventions": [bien, bien,
               {"code": "NO_EXISTE", "start_day": 1}]}).get_json()
    assert mal["valido"] is False
    assert any(e.startswith("Intervención 2:") and "traslapa" in e for e in mal["errores"])
    assert any(e.startswith("Intervención 3:") for e in mal["errores"])


def test_campo_desconocido_solo_avisa(cliente, analista):
    datos = post(cliente, analista, {**VALIDO, "otro": 1}).get_json()
    assert datos["valido"] is True and any("otro" in a for a in datos["avisos"])


@pytest.mark.parametrize("cuerpo", [[1, 2], {**VALIDO, "name": {"x": 1}},
                                    {**VALIDO, "population_by_age": 5},
                                    {**VALIDO, "interventions": ["texto"]}])
def test_cuerpo_mal_formado_es_422(cliente, analista, cuerpo):
    r = post(cliente, analista, cuerpo)
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"


def test_json_roto_400_y_tipo_415(cliente, analista):
    r = cliente.post("/api/v1/validate?format=json", data=b"{no", headers={**analista, "Content-Type": "application/json"})
    assert r.status_code == 400
    r = cliente.post("/api/v1/validate?format=json", data=b"x", headers={**analista, "Content-Type": "text/plain"})
    assert r.status_code == 415


def test_cuerpo_xml_y_respuesta_xml(cliente, analista):
    xml = (b"<escenario><name>Brote</name><disease_id>1</disease_id><region_id>1</region_id>"
           b"<population_size>100000</population_size><initial_infected>10</initial_infected>"
           b"<horizon_days>60</horizon_days><interventions>"
           b"<intervention><code>CIERRE_ESCUELAS</code><start_day>5</start_day></intervention>"
           b"</interventions></escenario>")
    r = cliente.post("/api/v1/validate", data=xml, headers={**analista, "Content-Type": "application/xml"})
    assert r.status_code == 200 and r.mimetype == "application/xml"
    assert b"<valido tipo=\"booleano\">true</valido>" in r.data
    r = cliente.post("/api/v1/validate?format=json", data=xml, headers={**analista, "Content-Type": "application/xml"})
    assert r.get_json()["valido"] is True


def test_xml_con_entidades_externas_se_rechaza(cliente, analista):
    xml = b'<!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><a><name>&x;</name></a>'
    r = cliente.post("/api/v1/validate?format=json", data=xml,
                     headers={**analista, "Content-Type": "application/xml"})
    assert r.status_code == 400


def test_sin_token_401_y_rol_ajeno_403(cliente, token):
    assert cliente.post("/api/v1/validate?format=json", json=VALIDO).status_code == 401
    r = post(cliente, token(roles=("OBSERVADOR",)), VALIDO)
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"
    assert cliente.get("/api/v1/versions/1/validation?format=json").status_code == 401
    assert cliente.get("/api/v1/versions/1/validation?format=json",
                       headers=token(roles=("X",))).status_code == 403


@pytest.mark.parametrize("rol", ["ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR"])
def test_roles_permitidos(cliente, token, rol):
    assert post(cliente, token(roles=(rol,)), VALIDO).status_code == 200


def test_redis_caido_es_503(cliente, analista, apagar_redis):
    apagar_redis()
    assert post(cliente, analista, VALIDO).status_code == 503


# ---- GET /versions/{id}/validation ---------------------------------------------------

@pytest.fixture
def version(monkeypatch):
    fila = {"id": 7, "scenario_id": 3, "version_number": 2, "status": "borrador"}
    detalle = {"version": {"id": 7}, "escenario": {"id": 3}}
    llamadas = []
    monkeypatch.setattr(queries, "get_version_simulacion", lambda i: fila if i == 7 else None)
    monkeypatch.setattr(queries, "get_escenario_detalle",
                        lambda s, n=None: llamadas.append((s, n)) or detalle)
    monkeypatch.setattr(queries, "revisa_version", lambda d: ([], ["aviso uno"]))
    return llamadas


def test_validacion_de_version(cliente, analista, version):
    r = cliente.get("/api/v1/versions/7/validation?format=json", headers=analista)
    assert r.status_code == 200
    assert r.get_json() == {"version_id": 7, "scenario_id": 3, "version_number": 2,
                            "status": "borrador", "valido": True, "errores": [],
                            "avisos": ["aviso uno"]}
    assert version == [(3, 2)]


def test_version_con_errores_sigue_siendo_200(cliente, analista, version, monkeypatch):
    monkeypatch.setattr(queries, "revisa_version", lambda d: (["malo"], []))
    datos = cliente.get("/api/v1/versions/7/validation?format=json", headers=analista).get_json()
    assert datos["valido"] is False and datos["errores"] == ["malo"]


def test_version_en_xml_por_defecto(cliente, analista, version):
    r = cliente.get("/api/v1/versions/7/validation", headers=analista)
    assert r.mimetype == "application/xml" and b"<validacion>" in r.data and b"<item>aviso uno</item>" in r.data


def test_version_inexistente_404_e_id_invalido_422(cliente, analista, version):
    r = cliente.get("/api/v1/versions/99/validation?format=json", headers=analista)
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"
    assert cliente.get("/api/v1/versions/abc/validation?format=json", headers=analista).status_code == 422


def test_validacion_no_audita_ni_escribe(cliente, analista, version):
    # log_audit, execute y get_conn explotan si se llaman (ver fixture cliente).
    assert cliente.get("/api/v1/versions/7/validation?format=json", headers=analista).status_code == 200
    assert post(cliente, analista, VALIDO).status_code == 200


# ---- contrato ------------------------------------------------------------------------

CONTRATOS = __import__("pathlib").Path(__file__).resolve().parents[3] / "docs/contratos/validacion"


def test_openapi_servido_es_el_del_contrato(cliente):
    servido = cliente.get("/openapi.json").data
    assert servido == (CONTRATOS / "openapi.json").read_bytes()
    spec = __import__("json").loads(servido)
    operaciones = {op["operationId"] for ruta in spec["paths"].values() for op in ruta.values()}
    assert operaciones == {"validar_escenario", "validar_version"}
    rutas_flask = {r.rule for r in cliente.application.url_map.iter_rules() if r.rule.startswith("/api/")}
    assert rutas_flask == {"/api/v1/validate", "/api/v1/versions/<version_id>/validation"}


@pytest.mark.parametrize("nombre,valido", [("validar_escenario", True), ("validar_escenario_invalido", False)])
def test_ejemplos_de_peticion_se_aceptan_y_dan_la_respuesta_del_ejemplo(cliente, analista, nombre, valido):
    ejemplos = CONTRATOS / "ejemplos"
    json_ = __import__("json")
    esperado = json_.loads((ejemplos / (nombre + ".json")).read_text(encoding="utf-8"))
    assert esperado["valido"] is valido
    for sufijo, tipo in (("json", "application/json"), ("xml", "application/xml")):
        r = cliente.post("/api/v1/validate?format=json", headers={**analista, "Content-Type": tipo},
                         data=(ejemplos / (nombre + ".peticion." + sufijo)).read_bytes())
        assert r.status_code == 200 and r.get_json()["valido"] is valido, r.data
    # El ejemplo de respuesta en XML es exactamente lo que serializa el servicio.
    from epidemia_comun.formatos import a_xml
    assert a_xml(esperado, "validacion").decode() == (
        ejemplos / (nombre + ".xml")).read_text(encoding="utf-8").rstrip("\n")
