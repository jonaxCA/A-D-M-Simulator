import json
from contextlib import contextmanager
from xml.etree import ElementTree as ET

import pytest

from backend_web import queries
from microservicios.parametros import rutas

COVID = {
    "r0": {"valor": 2.5, "fuente": "Liu et al. 2020", "supuesto": False},
    "incubacion_dias": {"valor": 5.1, "fuente": "Lauer et al. 2020", "supuesto": False},
    "letalidad_por_edad": {"0-19": 0.0001, "80+": 0.08},
}


class BaseFalsa:
    def __init__(self):
        self.params = {1: json.loads(json.dumps(COVID)),
                       2: {"r0": {"valor": 1.3, "fuente": "Biggerstaff et al. 2014", "supuesto": False}}}
        self.sentencias = []

    def ejecutar(self, sql, p):
        self.sentencias.append(sql)
        if sql.startswith("SELECT default_params FROM diseases"):
            return [(self.params[p[0]],)] if p[0] in self.params else []
        if sql.startswith("UPDATE diseases SET default_params"):
            self.params[p[1]] = json.loads(p[0])
        return []


class Cursor:
    def __init__(self, base):
        self.base, self.filas = base, []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, sql, params=()):
        self.filas = self.base.ejecutar(" ".join(sql.split()), params)

    def fetchone(self):
        return self.filas[0] if self.filas else None


class Conexion:
    def __init__(self, base):
        self.base = base

    def cursor(self):
        return Cursor(self.base)

    def commit(self):
        pass


@pytest.fixture
def base(monkeypatch):
    falsa = BaseFalsa()

    @contextmanager
    def get_conn():
        yield Conexion(falsa)

    monkeypatch.setattr(rutas, "get_conn", get_conn)
    monkeypatch.setattr(queries, "get_enfermedad",
                        lambda i: {"id": i, "default_params": falsa.params[i]} if i in falsa.params else None)
    return falsa


@pytest.fixture
def bitacora(monkeypatch):
    eventos = []
    monkeypatch.setattr(rutas, "log_audit",
                        lambda ctx, accion, entidad, entity_id=None, data_before=None,
                        data_after=None, **_: eventos.append(
                            (ctx.user_id, accion, entidad, entity_id, data_before, data_after)))
    return eventos


@pytest.fixture
def cliente(crear_cliente, base, bitacora):
    return crear_cliente("parametros")


@pytest.fixture
def epidemiologo(token):
    return token(roles=("EPIDEMIOLOGO",))


def test_consulta_xml_por_omision(cliente):
    r = cliente.get("/api/v1/diseases/2/parameters")
    assert r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "parametros"
    assert raiz.find("parametros").find("r0").findtext("valor") == "1.3"


def test_xml_valido_con_letalidad_por_edad(cliente):
    respuesta = cliente.get("/api/v1/diseases/1/parameters")
    assert respuesta.status_code == 200
    raiz = ET.fromstring(respuesta.data)
    assert raiz.find(".//entrada[@clave='0-19']").text == "0.0001"
    assert raiz.find(".//entrada[@clave='80+']").text == "0.08"


def test_consulta_json_con_format_y_con_accept(cliente):
    assert cliente.get("/api/v1/diseases/1/parameters?format=json").get_json()["parametros"]["r0"]["valor"] == 2.5
    r = cliente.get("/api/v1/diseases/1/parameters", headers={"Accept": "application/json"})
    assert r.content_type.startswith("application/json")


def test_format_invalido_es_400(cliente):
    assert cliente.get("/api/v1/diseases/1/parameters?format=csv").status_code == 400


def test_no_encontrada_es_404(cliente):
    assert cliente.get("/api/v1/diseases/9/parameters?format=json").status_code == 404
    assert cliente.get("/api/v1/diseases/9/parameters/status?format=json").status_code == 404


def test_estado_dice_que_falta_para_simular(cliente):
    datos = cliente.get("/api/v1/diseases/1/parameters/status?format=json").get_json()
    estados = {d["clave"]: d["estado"] for d in datos["detalle"]}
    assert estados["r0"] == "con_fuente" and estados["letalidad"] == "por_grupo"
    assert "infeccioso_dias" in datos["faltan"]


def test_escritura_sin_token_401_y_analista_403(cliente, token):
    cuerpo = {"parametros": {"r0": {"valor": 2.0, "supuesto": True}}}
    assert cliente.put("/api/v1/diseases/1/parameters?format=json", json=cuerpo).status_code == 401
    r = cliente.put("/api/v1/diseases/1/parameters?format=json", json=cuerpo,
                    headers=token(roles=("ANALISTA",)))
    assert r.status_code == 403


def test_guardar_con_fuente_conserva_lo_demas_y_audita(cliente, epidemiologo, base, bitacora):
    r = cliente.put("/api/v1/diseases/1/parameters?format=json", headers=epidemiologo, json={
        "parametros": {"infeccioso_dias": {"valor": 7, "fuente": "He et al. 2020"},
                       "tasa_hospitalizacion": {"valor": 0.04, "supuesto": True}}})
    assert r.status_code == 200
    guardados = base.params[1]
    assert guardados["infeccioso_dias"] == {"valor": 7, "fuente": "He et al. 2020", "supuesto": False}
    assert guardados["r0"] == COVID["r0"] and guardados["letalidad_por_edad"] == COVID["letalidad_por_edad"]
    assert bitacora == [(7, "UPDATE", "diseases", 1, {"default_params": COVID},
                         {"default_params": guardados})]


def test_solo_escribe_default_params(cliente, epidemiologo, base):
    cliente.put("/api/v1/diseases/1/parameters?format=json", headers=epidemiologo,
                json={"parametros": {"r0": {"valor": 1.9, "supuesto": True}}})
    updates = [s for s in base.sentencias if s.startswith("UPDATE")]
    assert updates == ["UPDATE diseases SET default_params=%s::jsonb WHERE id=%s"]


def test_guardar_en_xml(cliente, epidemiologo, base):
    xml = (b"<solicitud><parametros><r0><valor>1.8</valor><fuente>Estudio NL</fuente>"
           b"<supuesto>false</supuesto></r0></parametros></solicitud>")
    r = cliente.put("/api/v1/diseases/1/parameters?format=json",
                    headers={**epidemiologo, "Content-Type": "application/xml"}, data=xml)
    assert r.status_code == 200
    assert base.params[1]["r0"] == {"valor": 1.8, "fuente": "Estudio NL", "supuesto": False}


@pytest.mark.parametrize("parametro", [
    {"valor": 2.0},
    {"valor": 2.0, "fuente": "   "},
    {"valor": 2.0, "supuesto": False},
])
def test_exige_fuente_o_marca_de_supuesto(cliente, epidemiologo, base, bitacora, parametro):
    r = cliente.put("/api/v1/diseases/1/parameters?format=json", headers=epidemiologo,
                    json={"parametros": {"r0": parametro}})
    assert r.status_code == 422 and "fuente o marcar supuesto" in r.get_json()["detail"]
    assert base.params[1] == COVID and bitacora == []


@pytest.mark.parametrize("cuerpo", [
    {"parametros": {"r0": {"valor": 25, "supuesto": True}}},
    {"parametros": {"inventado": {"valor": 1, "supuesto": True}}},
    {"parametros": {"tasa_hospitalizacion": {"valor": 4, "supuesto": True}}},
    {"parametros": {}, "name": "otro"},
    {"r0": {"valor": 2, "supuesto": True}},
])
def test_valores_invalidos_son_422(cliente, epidemiologo, cuerpo):
    r = cliente.put("/api/v1/diseases/1/parameters?format=json", headers=epidemiologo, json=cuerpo)
    assert r.status_code == 422


def test_guardar_en_inexistente_es_404(cliente, epidemiologo):
    r = cliente.put("/api/v1/diseases/9/parameters?format=json", headers=epidemiologo,
                    json={"parametros": {"r0": {"valor": 2, "supuesto": True}}})
    assert r.status_code == 404
