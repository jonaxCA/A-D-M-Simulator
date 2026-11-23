import copy

import pytest

from backend_web import queries
from microservicios.validacion import huella
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
HUELLA = "9c56cc51b374c3ba189210d5b6d4bf57790d351c96c47c02190ecf1e430635ab"

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
    monkeypatch.setattr(huella, "de_version", lambda i: HUELLA if i == 7 else None)
    return llamadas


def test_validacion_de_version(cliente, analista, version):
    r = cliente.get("/api/v1/versions/7/validation?format=json", headers=analista)
    assert r.status_code == 200
    assert r.get_json() == {"version_id": 7, "scenario_id": 3, "version_number": 2,
                            "status": "borrador", "valido": True, "errores": [],
                            "avisos": ["aviso uno"], "huella": HUELLA}
    assert version == [(3, 2)]


def test_version_con_errores_sigue_siendo_200(cliente, analista, version, monkeypatch):
    monkeypatch.setattr(queries, "revisa_version", lambda d: (["malo"], []))
    datos = cliente.get("/api/v1/versions/7/validation?format=json", headers=analista).get_json()
    assert datos["valido"] is False and datos["errores"] == ["malo"]


def test_version_en_xml_por_defecto(cliente, analista, version):
    r = cliente.get("/api/v1/versions/7/validation", headers=analista)
    assert r.mimetype == "application/xml" and b"<validacion>" in r.data and b"<avisos><aviso>aviso uno</aviso></avisos>" in r.data


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


# ---- huella de la versión (D55) ------------------------------------------------------

FILA_VERSION = {"id": 7, "scenario_id": 3, "version_number": 2, "status": "en_revision",
                "population_size": 100000, "horizon_days": 60, "initial_infected": 10,
                "population_by_age": None, "population_age_unknown": 0, "age_unknown_policy": None,
                "disease_params": None, "default_params": None}
# Parámetros como los guarda diseases.default_params, todos marcados como supuesto (regla 8).
PARAMETROS = {clave: {"valor": valor, "fuente": "Supuesto de la prueba", "supuesto": True}
              for clave, valor in (("r0", 1.6), ("incubacion_dias", 2.0), ("infeccioso_dias", 5.0),
                                   ("letalidad", 0.001), ("tasa_hospitalizacion", 0.01),
                                   ("dias_hospitalizacion", 5.0))}
FILAS_INTERVENCION = [{"start_day": 5, "end_day": 20, "coverage": __import__("decimal").Decimal("0.800"),
                       "compliance": None, "params": {"reduccion": 0.5}, "code": "CIERRE_ESCUELAS"}]


def _base_falsa(consultas):
    def query(sql, params=(), one=False):
        consultas.append(" ".join(sql.split()))
        if "FROM scenario_versions" in sql:
            return dict(FILA_VERSION, disease_params=copy.deepcopy(PARAMETROS))
        return [dict(f) for f in FILAS_INTERVENCION]
    return query


def test_la_huella_es_la_misma_que_calcula_el_simulador(monkeypatch):
    from microservicios.simulador import datos as simulador_datos
    from microservicios.simulador import ejecucion
    from procesamiento.contrato import huella as canonica
    nuestras, suyas = [], []
    monkeypatch.setattr(huella, "query", _base_falsa(nuestras))
    monkeypatch.setattr(simulador_datos, "query", _base_falsa(suyas))
    calculada = huella.de_version(7)
    # El simulador solo corre aprobadas; la entrada es la misma con cualquier estado.
    FILA_VERSION["status"] = "aprobado"
    try:
        escenario, _, errores = ejecucion.escenario_de_version(7)
    finally:
        FILA_VERSION["status"] = "en_revision"
    assert errores == [] and calculada == canonica(escenario)
    assert nuestras == suyas      # la copia de version_para_motor sigue igual


def test_sin_version_no_hay_huella(monkeypatch):
    monkeypatch.setattr(huella, "query", lambda sql, params=(), one=False: None if one else [])
    assert huella.de_version(99) is None


def test_con_la_base_la_huella_coincide_con_la_del_simulador():
    from microservicios.pruebas_bd import tiene_base
    if not tiene_base():
        pytest.skip("Requiere la base de pruebas")
    from epidemia_comun.bd import query
    from microservicios.simulador import ejecucion
    from procesamiento.contrato import huella as canonica
    fila = query("SELECT id FROM scenario_versions WHERE status = 'aprobado' ORDER BY id LIMIT 1", one=True)
    if fila is None:
        pytest.skip("La semilla no trae una versión aprobada")
    escenario, _, errores = ejecucion.escenario_de_version(fila["id"])
    assert errores == [] and huella.de_version(fila["id"]) == canonica(escenario)
