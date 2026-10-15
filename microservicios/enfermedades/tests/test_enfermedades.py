from contextlib import contextmanager
from xml.etree import ElementTree as ET

import psycopg2
import pytest

from backend_web import queries
from microservicios.enfermedades import rutas

LISTADO = {"enfermedades": [{"id": 1, "code": "SARS_COV_2_ANCESTRAL", "nombre": "COVID-19",
                             "activa": True, "actividad": "con_casos"}],
           "total": 1, "pagina": 1, "por_pagina": 10, "paginas": 1, "desde": 1, "hasta": 1}


class BaseFalsa:
    def __init__(self):
        self.diseases = {1: {"code": "SARS_COV_2_ANCESTRAL", "name": "COVID-19",
                             "description": None, "is_active": True}}
        self.sentencias = []
        self.commits = 0

    def ejecutar(self, sql, p):
        self.sentencias.append(sql)
        if sql.startswith("INSERT INTO diseases"):
            if any(d["code"] == p[0] for d in self.diseases.values()):
                raise psycopg2.errors.UniqueViolation("uq_diseases_code")
            nuevo = max(self.diseases) + 1
            self.diseases[nuevo] = {"code": p[0], "name": p[1], "description": p[2],
                                    "is_active": True}
            return [(nuevo,)]
        if sql.startswith("SELECT id, name, description FROM diseases"):
            d = self.diseases.get(p[0])
            return [(p[0], d["name"], d["description"])] if d else []
        if sql.startswith("SELECT is_active FROM diseases"):
            d = self.diseases.get(p[0])
            return [(d["is_active"],)] if d else []
        if sql.startswith("UPDATE diseases SET name"):
            self.diseases[p[2]].update(name=p[0], description=p[1])
        elif sql.startswith("UPDATE diseases SET is_active"):
            self.diseases[p[1]]["is_active"] = p[0]
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
        self.base.commits += 1


@pytest.fixture
def base(monkeypatch):
    falsa = BaseFalsa()

    @contextmanager
    def get_conn():
        yield Conexion(falsa)

    monkeypatch.setattr(rutas, "get_conn", get_conn)
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
def cliente(crear_cliente, base, bitacora, monkeypatch):
    pedidos = []
    monkeypatch.setattr(queries, "get_enfermedades",
                        lambda **f: pedidos.append(f) or LISTADO)
    monkeypatch.setattr(queries, "get_enfermedad",
                        lambda i: {"id": 1, "code": "SARS_COV_2_ANCESTRAL", "name": "COVID-19",
                                   "description": None, "is_active": True,
                                   "created_at": "2026-09-01T00:00:00",
                                   "default_params": {}} if i == 1 else None)
    c = crear_cliente("enfermedades")
    c.pedidos = pedidos
    return c


@pytest.fixture
def epidemiologo(token):
    return token(roles=("EPIDEMIOLOGO",))


def test_lista_xml_por_omision(cliente):
    r = cliente.get("/api/v1/diseases")
    assert r.status_code == 200 and r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "catalogo_enfermedades"
    assert raiz.find("enfermedades").find("enfermedad").findtext("code") == "SARS_COV_2_ANCESTRAL"


def test_lista_xml_valido_con_letalidad_por_edad(cliente, monkeypatch):
    con_edades = {**LISTADO["enfermedades"][0],
                  "parametros": {"informativos": [{"valor": {"0-19": 0.0001, "80+": 0.08}}]}}
    monkeypatch.setattr(queries, "get_enfermedades", lambda **f: dict(LISTADO, enfermedades=[con_edades]))
    respuesta = cliente.get("/api/v1/diseases")
    assert respuesta.status_code == 200
    raiz = ET.fromstring(respuesta.data)
    assert raiz.find(".//entrada[@clave='0-19']").text == "0.0001"
    assert raiz.find(".//entrada[@clave='80+']").text == "0.08"


def test_lista_json_con_format_y_con_accept(cliente):
    assert cliente.get("/api/v1/diseases?format=json").get_json()["total"] == 1
    r = cliente.get("/api/v1/diseases", headers={"Accept": "application/json"})
    assert r.content_type.startswith("application/json")


def test_format_invalido_es_400(cliente):
    r = cliente.get("/api/v1/diseases?format=yaml")
    assert r.status_code == 400
    assert r.content_type.startswith("application/problem")


def test_lista_pasa_los_filtros(cliente):
    cliente.get("/api/v1/diseases?q=covid&status=activa&page=2&size=5&format=json")
    assert cliente.pedidos == [{"busqueda": "covid", "estado": "activa", "pagina": 2, "por_pagina": 5}]


@pytest.mark.parametrize("consulta", ["size=101", "page=0", "status=borrada", "size=x"])
def test_filtros_invalidos_son_422(cliente, consulta):
    assert cliente.get("/api/v1/diseases?format=json&" + consulta).status_code == 422


def test_detalle_y_no_encontrado(cliente):
    datos = cliente.get("/api/v1/diseases/1?format=json").get_json()
    assert datos["code"] == "SARS_COV_2_ANCESTRAL" and "default_params" not in datos
    r = cliente.get("/api/v1/diseases/99?format=json")
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"


def test_escritura_sin_token_401_y_analista_403(cliente, token):
    cuerpo = {"code": "DENGUE", "name": "Dengue"}
    assert cliente.post("/api/v1/diseases?format=json", json=cuerpo).status_code == 401
    r = cliente.post("/api/v1/diseases?format=json", json=cuerpo, headers=token(roles=("ANALISTA",)))
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


def test_alta_en_json_audita(cliente, epidemiologo, base, bitacora):
    r = cliente.post("/api/v1/diseases?format=json", headers=epidemiologo,
                     json={"code": "DENGUE", "name": " Dengue ", "description": "Arbovirosis"})
    assert r.status_code == 201
    nuevo = r.get_json()["id"]
    assert base.diseases[nuevo]["name"] == "Dengue" and base.commits == 1
    assert bitacora == [(7, "CREATE", "diseases", nuevo, None, {"code": "DENGUE", "name": "Dengue"})]


def test_alta_en_xml(cliente, epidemiologo, base):
    r = cliente.post("/api/v1/diseases?format=json", headers={**epidemiologo, "Content-Type": "application/xml"},
                     data=b"<solicitud><code>INFLUENZA_B</code><name>Influenza B</name></solicitud>")
    assert r.status_code == 201
    assert base.diseases[r.get_json()["id"]]["code"] == "INFLUENZA_B"


@pytest.mark.parametrize("cuerpo", [
    {"code": "dengue", "name": "Dengue"},
    {"code": "DENGUE"},
    {"code": "DENGUE", "name": "Dengue", "default_params": {}},
    {"code": 5, "name": "Dengue"},
])
def test_alta_invalida_es_422(cliente, epidemiologo, base, cuerpo):
    r = cliente.post("/api/v1/diseases?format=json", headers=epidemiologo, json=cuerpo)
    assert r.status_code == 422
    assert not any(s.startswith("INSERT") for s in base.sentencias)


def test_codigo_duplicado_es_409(cliente, epidemiologo):
    r = cliente.post("/api/v1/diseases?format=json", headers=epidemiologo,
                     json={"code": "SARS_COV_2_ANCESTRAL", "name": "Otra"})
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"


def test_cuerpo_que_no_es_json_ni_xml(cliente, epidemiologo):
    r = cliente.post("/api/v1/diseases?format=json", headers={**epidemiologo, "Content-Type": "text/plain"},
                     data=b"code=DENGUE")
    assert r.status_code == 415


def test_editar_no_cambia_el_codigo(cliente, epidemiologo, base, bitacora):
    r = cliente.put("/api/v1/diseases/1?format=json", headers=epidemiologo,
                    json={"code": "OTRO", "name": "COVID-19"})
    assert r.status_code == 422
    r = cliente.put("/api/v1/diseases/1?format=json", headers=epidemiologo,
                    json={"name": "COVID-19 (ancestral)", "description": "Variante original"})
    assert r.status_code == 200
    assert base.diseases[1]["code"] == "SARS_COV_2_ANCESTRAL"
    assert not any("code" in s for s in base.sentencias if s.startswith("UPDATE"))
    assert bitacora[-1][1:4] == ("UPDATE", "diseases", 1)
    assert bitacora[-1][5]["name"] == "COVID-19 (ancestral)"


def test_editar_inexistente_es_404(cliente, epidemiologo):
    r = cliente.put("/api/v1/diseases/99?format=json", headers=epidemiologo, json={"name": "X"})
    assert r.status_code == 404


def test_desactivar_es_baja_logica(cliente, epidemiologo, base, bitacora):
    r = cliente.post("/api/v1/diseases/1/deactivate?format=json", headers=epidemiologo)
    assert r.status_code == 200 and r.get_json()["is_active"] is False
    assert base.diseases[1]["is_active"] is False
    assert not any(s.startswith("DELETE") for s in base.sentencias)
    assert bitacora[-1][4:] == ({"is_active": True}, {"is_active": False})
    assert cliente.post("/api/v1/diseases/1/activate?format=json", headers=epidemiologo).get_json()["is_active"]


def test_accion_desconocida_es_404(cliente, epidemiologo):
    assert cliente.post("/api/v1/diseases/1/delete?format=json", headers=epidemiologo).status_code == 404


def test_no_hay_ruta_delete(cliente, epidemiologo):
    assert cliente.delete("/api/v1/diseases/1?format=json", headers=epidemiologo).status_code == 405
