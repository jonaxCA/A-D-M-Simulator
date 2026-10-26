import json
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import requests
import xmlschema

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import a_xml, de_xml
from microservicios.escenarios_xml import lectura, mapeo, rutas

RAIZ = Path(__file__).resolve().parents[3]
CONTRATO = RAIZ / "docs/contratos/escenarios-xml"
EJEMPLOS = CONTRATO / "ejemplos"
XSD = xmlschema.XMLSchema(str(CONTRATO / "escenario.xsd"))
XSD_ERROR = xmlschema.XMLSchema(str(RAIZ / "docs/contratos/comun/error.xsd"))

ESCENARIO = {"id": 5, "name": "Brote en Monterrey", "description": "Con cierre y vacunación",
             "disease_code": "INFLUENZA_A_H1N1", "disease_name": "Influenza A",
             "region_code": "19039", "region_name": "Monterrey"}
VERSION = {"id": 31, "version_number": 2, "status": "borrador", "is_current": True,
           "population_size": 100000, "horizon_days": 180, "initial_infected": 10,
           "notes": "Notas & <ejemplo>",
           "population_by_age": {"0-19": 28000, "20-39": 31000, "40-59": 24000,
                                 "60-79": 12000, "80+": 3000},
           "population_age_unknown": 2000, "age_unknown_policy": "prorratear"}
INTERVENCIONES = [
    {"id": 1, "order_index": 0, "start_day": 20, "end_day": 60, "coverage": Decimal("0.800"),
     "compliance": Decimal("0.900"), "params": {"reduccion": 0.8, "sectores": ["a", "b"]},
     "type_code": "CIERRE_TRABAJO", "region_code": None},
    {"id": 2, "order_index": 1, "start_day": 30, "end_day": None, "coverage": None,
     "compliance": None, "params": {"eficacia": 0.6, "dosis_diarias": 500, "prioridad": "edad_desc",
                                    "activa": True},
     "type_code": "VACUNACION", "region_code": "19039"}]
IDS = {"CIERRE_TRABAJO": 4, "VACUNACION": 5}


class BD:
    """Base falsa: responde a las consultas de lectura.py según su SQL."""

    def __init__(self):
        self.version = dict(VERSION)
        self.existe = True
        self.peticiones = []

    def query(self, sql, params=None, one=False):
        sql = " ".join(sql.split())
        self.peticiones.append((sql, params))
        if "FROM scenarios s" in sql:
            return ESCENARIO if self.existe else None
        if "FROM scenario_versions" in sql:
            pedida = params[1] if len(params) > 1 else None
            if pedida is not None and pedida != self.version["version_number"]:
                return None
            return self.version
        if "FROM scenario_interventions" in sql:
            return [dict(i) for i in INTERVENCIONES]
        if "FROM diseases" in sql:
            return {"id": 1} if params[0] == "INFLUENZA_A_H1N1" else None
        if "FROM regions" in sql:
            return [{"id": 9, "code": c} for c in params[0] if c in ("19039", "19026")]
        if "FROM intervention_types" in sql:
            return [{"id": IDS[c], "code": c} for c in params[0] if c in IDS]
        raise AssertionError(sql)


def respuesta(estado, cuerpo, xml=False):
    r = requests.Response()
    r.status_code = estado
    if xml:
        r._content = a_xml(cuerpo, "respuesta")
        r.headers["Content-Type"] = "application/xml"
    else:
        r._content = json.dumps(cuerpo).encode()
        r.headers["Content-Type"] = "application/json"
    return r


class Servicios:
    """llamar() simulado: registra las llamadas y responde por servicio."""

    def __init__(self):
        self.llamadas = []
        self.validacion = lambda cuerpo: respuesta(200, {"errores": [], "avisos": ["Aviso de prueba"]})
        self.escenarios = lambda cuerpo: respuesta(201, {"id": 12, "version_number": 1, "status": "borrador"}, xml=True)
        self.intervenciones = lambda cuerpo, n: respuesta(201, {"id": 100 + n}, xml=True)
        self.detalle = lambda: respuesta(200, {"version": {"id": 31}})
        self.caido = None

    def __call__(self, servicio, metodo, ruta, formato="json", cuerpo=None, **_):
        self.llamadas.append((servicio, metodo, ruta, formato, cuerpo))
        if self.caido == servicio:
            raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio no respondió.")
        if servicio == "validacion":
            return self.validacion(cuerpo)
        if servicio == "escenarios" and metodo == "GET":
            return self.detalle()
        if servicio == "escenarios":
            return self.escenarios(cuerpo)
        n = len([c for c in self.llamadas if c[0] == "intervenciones"])
        return self.intervenciones(cuerpo, n)

    def de(self, servicio):
        return [c for c in self.llamadas if c[0] == servicio]


@pytest.fixture
def bd(monkeypatch):
    falsa = BD()
    monkeypatch.setattr(lectura, "query", falsa.query)
    return falsa


@pytest.fixture
def auditoria(monkeypatch):
    eventos = {"audit": [], "commits": 0}

    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    class Conn:
        def cursor(self):
            return Cur()

        def commit(self):
            eventos["commits"] += 1

    @contextmanager
    def get_conn():
        yield Conn()

    def log_audit(ctx, accion, entidad, entity_id=None, data_before=None, data_after=None, cur=None):
        assert cur is not None, "la bitácora debe ir en el mismo cursor"
        eventos["audit"].append((ctx.user_id, accion, entidad, entity_id, data_after))

    monkeypatch.setattr(rutas, "get_conn", get_conn)
    monkeypatch.setattr(rutas, "log_audit", log_audit)
    return eventos


@pytest.fixture
def servicios(monkeypatch):
    s = Servicios()
    monkeypatch.setattr(rutas, "llamar", s)
    return s


@pytest.fixture
def cliente(crear_cliente, bd, auditoria, servicios):
    return crear_cliente("escenarios_xml")


@pytest.fixture
def analista(token):
    return token(roles=("ANALISTA",))


def xml_ejemplo():
    return (EJEMPLOS / "importar_escenario.xml").read_bytes()


def importar(cliente, headers, cuerpo=None, tipo="application/xml", ruta="/api/v1/scenarios/import"):
    return cliente.post(ruta, data=xml_ejemplo() if cuerpo is None else cuerpo,
                        headers=dict(headers, **{"Content-Type": tipo}))


# ------------------------------------------------------------------------- exportar

def test_export_ok_valida_contra_xsd_y_audita(cliente, analista, bd, auditoria):
    r = cliente.get("/api/v1/scenarios/5/export", headers=analista)
    assert r.status_code == 200 and r.content_type.startswith("application/xml")
    assert "escenario-5-v2.xml" in r.headers["Content-Disposition"]
    assert list(XSD.iter_errors(r.data)) == []
    raiz = ET.fromstring(r.data)
    assert raiz.findtext("nombre") == "Brote en Monterrey"
    assert raiz.find("enfermedad").get("codigo") == "INFLUENZA_A_H1N1"
    assert raiz.find("version").get("numero") == "2"
    assert [g.get("edad") for g in raiz.iter("grupo")] == list(mapeo.GRUPOS_EDAD)
    assert raiz.findtext("version/notas") == "Notas & <ejemplo>"
    assert len(raiz.findall("version/intervenciones/intervencion")) == 2
    assert auditoria["audit"] == [(7, "EXPORT", "scenarios", 5, {"version_number": 2, "formato": "xml"})]
    assert auditoria["commits"] == 1


def test_export_version_pedida(cliente, analista, bd):
    assert cliente.get("/api/v1/scenarios/5/export?version=2", headers=analista).status_code == 200
    r = cliente.get("/api/v1/scenarios/5/export?version=9", headers=analista)
    assert r.status_code == 404


def test_export_404_no_audita(cliente, analista, bd, auditoria):
    bd.existe = False
    r = cliente.get("/api/v1/scenarios/999/export", headers=analista)
    assert r.status_code == 404 and r.content_type.startswith("application/problem+xml")
    assert list(XSD_ERROR.iter_errors(r.data)) == []
    assert auditoria["audit"] == []


def test_export_sin_token_401(cliente):
    r = cliente.get("/api/v1/scenarios/5/export")
    assert r.status_code == 401 and ET.fromstring(r.data).findtext("codigo") == "TOKEN_AUSENTE"


def test_export_rol_sin_permiso_403(cliente, token, auditoria):
    r = cliente.get("/api/v1/scenarios/5/export", headers=token(roles=("INVITADO",)))
    assert r.status_code == 403 and auditoria["audit"] == []


@pytest.mark.parametrize("rol", ["ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR"])
def test_export_roles_permitidos(cliente, token, rol):
    assert cliente.get("/api/v1/scenarios/5/export", headers=token(roles=(rol,))).status_code == 200


def test_export_json_no_se_admite(cliente, analista):
    r = cliente.get("/api/v1/scenarios/5/export?format=json", headers=analista)
    assert r.status_code == 400 and r.content_type.startswith("application/problem+json")
    # Accept: application/json se ignora: el documento siempre es XML.
    r = cliente.get("/api/v1/scenarios/5/export", headers=dict(analista, Accept="application/json"))
    assert r.status_code == 200 and r.content_type.startswith("application/xml")


def test_export_version_invalida_422(cliente, analista):
    assert cliente.get("/api/v1/scenarios/5/export?version=abc", headers=analista).status_code == 422
    assert cliente.get("/api/v1/scenarios/5/export?version=0", headers=analista).status_code == 422


def test_export_poblacion_por_edad_incompleta_409(cliente, analista, bd):
    bd.version["population_by_age"] = {"0-4": 1}
    assert cliente.get("/api/v1/scenarios/5/export", headers=analista).status_code == 409


def test_export_sin_edad_ni_intervenciones(cliente, analista, bd, monkeypatch):
    bd.version.update(population_by_age=None, population_age_unknown=0, age_unknown_policy=None, notes=None)
    monkeypatch.setattr(lectura, "query", lambda sql, p=None, one=False:
                        [] if "FROM scenario_interventions" in sql else bd.query(sql, p, one))
    r = cliente.get("/api/v1/scenarios/5/export", headers=analista)
    assert r.status_code == 200 and list(XSD.iter_errors(r.data)) == []


# --------------------------------------------------------------------------- esquema

def test_xsd_publicado_sin_token(cliente):
    r = cliente.get("/api/v1/schemas/scenario.xsd")
    assert r.status_code == 200 and r.content_type.startswith("application/xml")
    assert r.data == (CONTRATO / "escenario.xsd").read_bytes()
    xmlschema.XMLSchema(r.data.decode("utf-8"))


# --------------------------------------------------------------------------- importar

def test_import_exitoso_crea_escenario_e_intervenciones(cliente, analista, servicios):
    r = importar(cliente, analista)
    assert r.status_code == 201, r.data
    assert r.content_type.startswith("application/xml")
    cuerpo = de_xml(r.data)
    assert cuerpo["scenario_id"] == 12 and cuerpo["version_id"] == 31
    assert cuerpo["intervenciones_creadas"] == 2
    orden = [(c[0], c[1], c[2], c[3]) for c in servicios.llamadas]
    assert orden == [("validacion", "POST", "/api/v1/validate", "json"),
                     ("escenarios", "POST", "/api/v1/scenarios", "xml"),
                     ("escenarios", "GET", "/api/v1/scenarios/12", "json"),
                     ("intervenciones", "POST", "/api/v1/versions/31/interventions", "json"),
                     ("intervenciones", "POST", "/api/v1/versions/31/interventions", "json")]
    esc = servicios.de("escenarios")[0][4]
    assert esc["disease_id"] == 1 and esc["region_id"] == 9 and esc["population_size"] == 100000
    # escenarios solo acepta sus campos de alta: la edad va como stratify + política
    assert esc["stratify"] is True and "grupos" not in esc and "population_by_age" not in esc
    assert esc["age_unknown_policy"] == "prorratear"
    # el cuerpo es plano y también se puede serializar como XML y leer de vuelta
    assert de_xml(a_xml(esc, "solicitud"))["name"] == "Brote de influenza en Monterrey"
    val = servicios.de("validacion")[0][4]
    assert "scenario" not in val and val["estratificar"] is True
    assert val["population_by_age"]["80+"] == 3000 and len(val["interventions"]) == 2
    i1, i2 = [c[4] for c in servicios.de("intervenciones")]
    assert i1 == {"code": "CIERRE_ESCUELAS", "start_day": 20, "end_day": 60, "coverage": 0.8,
                  "compliance": 0.9, "params": {"reduccion": 0.8}}
    assert "target_region_id" not in i2 and i2["params"]["dosis_diarias"] == 500
    assert "end_day" not in i2


IDS_DEL_EJEMPLO = {"CIERRE_ESCUELAS": 4, "VACUNACION": 5}


@pytest.fixture(autouse=True)
def tipos_del_ejemplo(monkeypatch):
    """El ejemplo usa CIERRE_ESCUELAS; se agrega al catálogo falso."""
    IDS["CIERRE_ESCUELAS"] = 4


def test_import_json_de_respuesta(cliente, analista):
    r = importar(cliente, analista, ruta="/api/v1/scenarios/import?format=json")
    assert r.status_code == 201 and r.get_json()["version_number"] == 1
    assert r.get_json()["avisos"][-1] == "Aviso de prueba"


def test_import_sin_version_en_alta_pide_el_detalle(cliente, analista, servicios):
    servicios.escenarios = lambda c: respuesta(201, {"id": 12}, xml=True)
    assert importar(cliente, analista).status_code == 201
    assert ("escenarios", "GET", "/api/v1/scenarios/12") == servicios.llamadas[2][:3]
    assert servicios.llamadas[3][2] == "/api/v1/versions/31/interventions"


def test_import_sin_token_401_y_rol_403(cliente, token, servicios):
    assert cliente.post("/api/v1/scenarios/import", data=xml_ejemplo(),
                        headers={"Content-Type": "application/xml"}).status_code == 401
    assert importar(cliente, token(roles=("INVITADO",))).status_code == 403
    assert servicios.llamadas == []


def test_import_xml_invalido_para_xsd_422_con_rutas(cliente, analista, servicios):
    malo = xml_ejemplo().replace(b"<cobertura>0.800</cobertura>", b"<cobertura>1.5</cobertura>")
    r = importar(cliente, analista, malo)
    assert r.status_code == 422 and r.content_type.startswith("application/problem+xml")
    assert list(XSD_ERROR.iter_errors(r.data)) == []
    errores = ET.fromstring(r.data).findall("errores/item")
    assert errores and "cobertura" in errores[0].findtext("ruta")
    assert servicios.llamadas == []
    j = importar(cliente, analista, malo, ruta="/api/v1/scenarios/import?format=json")
    assert j.get_json()["errores"][0]["ruta"].endswith("cobertura")


@pytest.mark.parametrize("reemplazo", [
    (b'edad="80+"', b'edad="85+"'),                       # enumeración
    (b"<horizonte_dias>180", b"<horizonte_dias>0"),       # rango
    (b'tipo="VACUNACION"', b'tipo="MAL TIPO"'),           # patrón
    (b'<grupo edad="80+">3000</grupo>', b""),             # faltan grupos
    (b"<nombre>Brote de influenza en Monterrey</nombre>", b"<nombre>  </nombre>"),
    (b'esquema="1.0"', b'esquema="2.0"'),
])
def test_import_violaciones_del_xsd(cliente, analista, reemplazo):
    r = importar(cliente, analista, xml_ejemplo().replace(*reemplazo))
    assert r.status_code == 422, r.data


def test_import_xml_mal_formado_400(cliente, analista):
    assert importar(cliente, analista, b"<escenario>").status_code == 400


def test_import_rechaza_dtd_y_entidades(cliente, analista):
    xxe = b'<?xml version="1.0"?><!DOCTYPE e [<!ENTITY x SYSTEM "file:///etc/passwd">]><escenario>&x;</escenario>'
    assert importar(cliente, analista, xxe).status_code == 400


def test_import_content_type_json_415(cliente, analista):
    assert importar(cliente, analista, b"{}", tipo="application/json").status_code == 415


def test_import_cuerpo_demasiado_grande_413(cliente, analista):
    assert importar(cliente, analista, b"<a>" + b"x" * (1024 * 1024) + b"</a>").status_code == 413


def test_import_reglas_entre_campos_422(cliente, analista, servicios):
    malo = xml_ejemplo().replace(b">28000<", b">27000<")
    r = importar(cliente, analista, malo)
    assert r.status_code == 422 and "suma" in ET.fromstring(r.data).findtext("detail")
    malo = xml_ejemplo().replace(b"<fin_dia>60", b"<fin_dia>10")
    assert importar(cliente, analista, malo).status_code == 422
    sin_politica = xml_ejemplo().replace(b' politica="prorratear"', b"")
    assert importar(cliente, analista, sin_politica).status_code == 422
    assert servicios.llamadas == []


def test_import_codigo_de_catalogo_inexistente_422(cliente, analista, servicios):
    r = importar(cliente, analista, xml_ejemplo().replace(b"INFLUENZA_A_H1N1", b"NO_EXISTE"))
    assert r.status_code == 422
    assert "/escenario/enfermedad/@codigo" in r.data.decode()
    assert servicios.llamadas == []


def test_import_errores_de_validacion_422_sin_crear(cliente, analista, servicios):
    servicios.validacion = lambda c: respuesta(200, {"errores": [
        {"campo": "initial_infected", "mensaje": "Demasiados infectados."}, "Otro error"]})
    r = importar(cliente, analista)
    assert r.status_code == 422
    fallas = ET.fromstring(r.data).findall("errores/item")
    assert [f.findtext("ruta") for f in fallas] == ["initial_infected", "/"]
    assert list(XSD_ERROR.iter_errors(r.data)) == []
    assert [c[0] for c in servicios.llamadas] == ["validacion"]


def test_import_validacion_responde_422_con_errores(cliente, analista, servicios):
    servicios.validacion = lambda c: respuesta(422, {"errores": ["Mal"], "detail": "x"})
    r = importar(cliente, analista)
    assert r.status_code == 422 and "Mal" in r.data.decode()


def test_import_validacion_caida_503(cliente, analista, servicios):
    servicios.caido = "validacion"
    r = importar(cliente, analista)
    assert r.status_code == 503 and ET.fromstring(r.data).findtext("codigo") == "SERVICIO_NO_DISPONIBLE"
    assert [c[0] for c in servicios.llamadas] == ["validacion"]


def test_import_escenarios_caido_o_5xx_503_sin_intervenciones(cliente, analista, servicios):
    servicios.caido = "escenarios"
    assert importar(cliente, analista).status_code == 503
    servicios.caido = None
    servicios.escenarios = lambda c: respuesta(500, {"detail": "boom"})
    assert importar(cliente, analista).status_code == 503
    assert servicios.de("intervenciones") == []


def test_import_nombre_duplicado_409(cliente, analista, servicios):
    servicios.escenarios = lambda c: respuesta(409, {"detail": "Ya existe."})
    r = importar(cliente, analista)
    assert r.status_code == 409 and ET.fromstring(r.data).findtext("codigo") == "CONFLICTO"


def test_import_falla_a_medias_reporta_estado_parcial(cliente, analista, servicios):
    servicios.intervenciones = lambda c, n: (respuesta(201, {"id": 1}, xml=True) if n == 1
                                             else respuesta(422, {"detail": "Se traslapa."}))
    r = importar(cliente, analista)
    assert r.status_code == 422
    detalle = ET.fromstring(r.data).findtext("detail")
    assert "escenario 12" in detalle and "1 de 2" in detalle and "orden 1" in detalle
    assert "No se reintentó" in detalle
    assert len(servicios.de("intervenciones")) == 2  # sin reintentos


def test_import_servicio_intervenciones_caido_a_medias_503(cliente, analista, servicios):
    servicios.caido = "intervenciones"
    r = importar(cliente, analista)
    assert r.status_code == 503 and "0 de 2" in ET.fromstring(r.data).findtext("detail")
    assert len(servicios.de("intervenciones")) == 1


# ------------------------------------------------------------------------ ida y vuelta

def test_ida_y_vuelta_exportar_importar_conserva_la_version(cliente, analista, servicios):
    exportado = cliente.get("/api/v1/scenarios/5/export", headers=analista).data
    r = importar(cliente, analista, exportado)
    assert r.status_code == 201, r.data
    esc = servicios.de("escenarios")[0][4]
    assert (esc["name"], esc["description"], esc["notes"]) == (
        ESCENARIO["name"], ESCENARIO["description"], VERSION["notes"])
    assert esc["population_size"] == VERSION["population_size"]
    assert esc["stratify"] is True
    assert (esc["horizon_days"], esc["initial_infected"], esc["age_unknown_policy"]) == (
        180, 10, "prorratear")
    val = servicios.de("validacion")[0][4]
    assert val["population_by_age"] == VERSION["population_by_age"]
    enviadas = [c[4] for c in servicios.de("intervenciones")]
    assert len(enviadas) == len(INTERVENCIONES)
    for original, enviada in zip(INTERVENCIONES, enviadas):
        assert enviada["code"] == original["type_code"]
        assert enviada["start_day"] == original["start_day"] and enviada.get("end_day") == original["end_day"]
        for campo, clave in (("coverage", "coverage"), ("compliance", "compliance")):
            esperado = original[campo]
            assert enviada.get(clave) == (None if esperado is None else float(esperado))
        assert enviada.get("params", {}) == original["params"]
        assert "target_region_id" not in enviada and "intervention_type_id" not in enviada


def test_ida_y_vuelta_es_estable_en_xml(bd):
    primero = mapeo.construir_documento(lectura.leer_escenario(5))
    doc, fallas = mapeo.leer_documento(ET.fromstring(primero))
    assert fallas == [] and mapeo.reglas_documento(doc) == []
    assert doc["numero_version"] == 2 and doc["por_edad"] == VERSION["population_by_age"]


# --------------------------------------------------------------------------- contrato

@pytest.mark.parametrize("nombre", ["importar_escenario", "exportar_escenario"])
def test_ejemplos_xml_del_escenario_validan(nombre):
    assert list(XSD.iter_errors(str(EJEMPLOS / (nombre + ".xml")))) == []


@pytest.mark.parametrize("ruta", [RAIZ / "docs/contratos/comun/ejemplos/error.xml",
                                  *sorted(EJEMPLOS.glob("*error*.xml"))])
def test_ejemplos_de_error_validan_contra_error_xsd(ruta):
    assert list(XSD_ERROR.iter_errors(str(ruta))) == []


def test_ejemplos_json_son_json_y_coinciden_con_su_xml():
    for ruta in EJEMPLOS.glob("*.json"):
        json.loads(ruta.read_text(encoding="utf-8"))
    j = json.loads((EJEMPLOS / "importar_escenario_error_422.json").read_text(encoding="utf-8"))
    x = ET.parse(EJEMPLOS / "importar_escenario_error_422.xml").getroot()
    assert x.findtext("detail") == j["detail"] and x.find("errores/item/ruta").text == j["errores"][0]["ruta"]


def test_el_xsd_rechaza_documentos_con_cobertura_fuera_de_rango_o_dia_negativo():
    for cambio in ((b"<cobertura>0.800", b"<cobertura>-0.1"), (b"<inicio_dia>20", b"<inicio_dia>-1"),
                   (b"<cumplimiento>0.900", b"<cumplimiento>1.0001")):
        assert list(XSD.iter_errors(xml_ejemplo().replace(*cambio).decode()))


def test_openapi_servido_es_el_del_contrato(cliente):
    r = cliente.get("/openapi.json")
    assert r.status_code == 200 and r.data == (CONTRATO / "openapi.json").read_bytes()
    doc = json.loads(r.data)
    assert set(doc["paths"]) == {"/api/v1/scenarios/{id}/export", "/api/v1/scenarios/import",
                                 "/api/v1/schemas/scenario.xsd"}
    for ruta in doc["paths"].values():
        for operacion in ruta.values():
            for respuesta_ in operacion["responses"].values():
                for tipo, contenido in respuesta_.get("content", {}).items():
                    assert "example" in contenido or "examples" in contenido, tipo


def test_health_y_docs(cliente):
    assert cliente.get("/docs").status_code == 200


def test_error_500_no_expone_detalle(cliente, analista, monkeypatch):
    monkeypatch.setattr(lectura, "query", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("SQL secreto")))
    r = cliente.get("/api/v1/scenarios/5/export", headers=analista)
    assert r.status_code == 500 and b"secreto" not in r.data
