import json
from contextlib import contextmanager
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from backend_web import queries
from epidemia_comun.formatos import a_xml
from microservicios.intervenciones import rutas

RAIZ = Path(__file__).resolve().parents[3]
CONTRATO = RAIZ / "docs/contratos/intervenciones"

TIPOS = [
    {"id": 1, "code": "CIERRE_ESCUELAS", "name": "Cierre de escuelas", "target_layer": "escuela",
     "param_schema": {"type": "object", "required": ["reduccion"], "properties": {
         "reduccion": {"type": "number", "minimum": 0, "maximum": 1}}}},
    {"id": 2, "code": "VACUNACION", "name": "Vacunación", "target_layer": "poblacion",
     "param_schema": {"type": "object", "properties": {
         "eficacia": {"type": "number", "minimum": 0, "maximum": 1},
         "grupos": {"type": "array"}}}},
]
EXISTENTE = {"id": 77, "start_day": 10, "end_day": 40, "coverage": 0.8, "compliance": 0.9,
             "params": {"reduccion": 0.5}, "order_index": 0, "code": "CIERRE_ESCUELAS",
             "name": "Cierre de escuelas", "target_layer": "escuela"}
NUEVA = {"code": "VACUNACION", "start_day": 20, "coverage": 0.6, "params": {"eficacia": 0.7}}


class Mundo:
    def __init__(self):
        self.version = {"id": 31, "scenario_id": 12, "version_number": 2, "status": "borrador",
                        "is_current": True, "horizon_days": 120, "owner_id": 7}
        self.filas = [dict(EXISTENTE)]
        self.llamadas = []
        self.auditoria = []
        self.sentencias = []
        self.commits = 0
        self.tipo_costo = (2, 100, "viejo", True)  # id, unit_cost, source, assumption
        self.resultado = (True, None)


@pytest.fixture
def mundo(monkeypatch):
    m = Mundo()

    def query(sql, params=(), one=False):
        if "FROM scenario_versions" in sql:
            return m.version if (params[0] == 31 and m.version) else None
        return list(m.filas)
    monkeypatch.setattr(rutas, "query", query)
    monkeypatch.setattr(queries, "get_tipos_intervencion", lambda: TIPOS)

    def agrega(version_id, datos, *, contexto):
        m.llamadas.append(("agrega", version_id, datos, contexto))
        if m.resultado[0]:
            m.filas.append({"id": 78, "start_day": datos["start_day"], "end_day": datos["end_day"],
                            "coverage": datos["coverage"], "compliance": datos["compliance"],
                            "params": datos["params"], "order_index": 1, "code": datos["code"],
                            "name": "Vacunación", "target_layer": "poblacion"})
        return m.resultado
    monkeypatch.setattr(queries, "agrega_intervencion", agrega)

    def quita(version_id, iid, *, contexto):
        m.llamadas.append(("quita", version_id, iid, contexto))
        return m.resultado
    monkeypatch.setattr(queries, "quita_intervencion", quita)

    def mueve(version_id, iid, direccion, *, contexto):
        m.llamadas.append(("mueve", version_id, iid, direccion, contexto))
        return m.resultado
    monkeypatch.setattr(queries, "mueve_intervencion", mueve)

    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, params=()):
            m.sentencias.append((" ".join(sql.split()), params))

        def fetchone(self):
            sql, params = m.sentencias[-1]
            if sql.startswith("SELECT t.id"):
                return m.tipo_costo if params[0] == 77 and params[1] == 31 else None

    class Conn:
        def cursor(self):
            return Cur()

        def commit(self):
            m.commits += 1

    @contextmanager
    def get_conn():
        yield Conn()
    monkeypatch.setattr(rutas, "get_conn", get_conn)

    def log_audit(contexto, accion, tipo, entidad, data_before=None, data_after=None, cur=None):
        m.auditoria.append((contexto, accion, tipo, entidad, data_before, data_after, cur))
    monkeypatch.setattr(rutas, "log_audit", log_audit)
    return m


@pytest.fixture
def cliente(crear_cliente):
    return crear_cliente("intervenciones")


def con_json(cuerpo):
    return {"data": json.dumps(cuerpo), "content_type": "application/json"}


BASE = "/api/v1/versions/31/interventions"


@pytest.mark.parametrize("metodo,ruta", [
    ("get", BASE), ("post", BASE), ("delete", BASE + "/77"),
    ("post", BASE + "/77/move"), ("put", BASE + "/77/cost")])
def test_sin_token_401_y_rol_ajeno_403(cliente, token, mundo, metodo, ruta):
    r = getattr(cliente, metodo)(ruta + "?format=json")
    assert r.status_code == 401
    r = getattr(cliente, metodo)(ruta + "?format=json", headers=token(("OTRO",)))
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


def test_listar_json_y_xml(cliente, token, mundo):
    r = cliente.get(BASE + "?format=json", headers=token())
    cuerpo = r.get_json()
    assert r.status_code == 200 and cuerpo["editable"] is True and cuerpo["total"] == 1
    assert cuerpo["intervenciones"][0]["code"] == "CIERRE_ESCUELAS"
    r = cliente.get(BASE, headers=token())
    assert r.mimetype == "application/xml"
    assert ET.fromstring(r.data).find("intervenciones/intervencion/id").text == "77"
    r = cliente.get(BASE, headers=dict(token(), Accept="application/json"))
    assert r.mimetype == "application/json"


def test_version_inexistente_404(cliente, token, mundo):
    r = cliente.get("/api/v1/versions/999/interventions?format=json", headers=token())
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"
    r = cliente.post("/api/v1/versions/999/interventions?format=json", headers=token(), **con_json(NUEVA))
    assert r.status_code == 404


def test_agregar_json_con_contexto_del_token(cliente, token, mundo):
    r = cliente.post(BASE + "?format=json", headers=token(), **con_json(NUEVA))
    assert r.status_code == 201
    assert r.get_json()["id"] == 78 and r.get_json()["params"] == {"eficacia": 0.7}
    _, version_id, datos, contexto = mundo.llamadas[0]
    assert version_id == 31 and datos["intervention_type_id"] == 2
    assert datos["params"] == {"eficacia": 0.7} and datos["coverage"] == 0.6
    assert contexto.user_id == 7  # la bitácora la escribe queries.agrega_intervencion


def test_agregar_xml(cliente, token, mundo):
    r = cliente.post(BASE, headers=token(), data=a_xml(dict(NUEVA, end_day=None), "intervencion"),
                     content_type="application/xml")
    assert r.status_code == 201 and r.mimetype == "application/xml"
    datos = mundo.llamadas[0][2]
    assert datos["start_day"] == 20 and datos["end_day"] is None and datos["params"] == {"eficacia": 0.7}


def test_agregar_params_vacios_en_xml_y_requerido_faltante(cliente, token, mundo):
    cuerpo = {"code": "VACUNACION", "start_day": 5, "params": {}}
    r = cliente.post(BASE, headers=token(), data=a_xml(cuerpo, "intervencion"),
                     content_type="application/xml")
    assert r.status_code == 201
    r = cliente.post(BASE + "?format=json", headers=token(),
                     **con_json({"code": "CIERRE_ESCUELAS", "start_day": 100}))
    assert r.status_code == 422 and "obligatorio" in r.get_json()["detail"]


def test_agregar_param_fuera_de_esquema_422(cliente, token, mundo):
    r = cliente.post(BASE + "?format=json", headers=token(),
                     **con_json(dict(NUEVA, params={"eficacia": 5})))
    assert r.status_code == 422 and "mayor" in r.get_json()["detail"]
    r = cliente.post(BASE + "?format=json", headers=token(),
                     **con_json(dict(NUEVA, params={"inventado": 1})))
    assert r.status_code == 422 and "inventado" in r.get_json()["detail"]
    assert not mundo.llamadas


def test_agregar_datos_invalidos_422(cliente, token, mundo):
    for cuerpo in (dict(NUEVA, code="NO_EXISTE"), dict(NUEVA, start_day=999),
                   dict(NUEVA, coverage=3), dict(NUEVA, end_day=1), dict(NUEVA, extra=1), [1]):
        r = cliente.post(BASE + "?format=json", headers=token(), **con_json(cuerpo))
        assert r.status_code == 422, cuerpo
    assert not mundo.llamadas


def test_agregar_traslape_409(cliente, token, mundo):
    r = cliente.post(BASE + "?format=json", headers=token(),
                     **con_json({"code": "CIERRE_ESCUELAS", "start_day": 20, "params": {"reduccion": 0.1}}))
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"


def test_agregar_json_invalido_400_y_tipo_415(cliente, token, mundo):
    r = cliente.post(BASE + "?format=json", headers=token(), data="{no", content_type="application/json")
    assert r.status_code == 400
    r = cliente.post(BASE + "?format=json", headers=token(), data="x", content_type="text/plain")
    assert r.status_code == 415


@pytest.mark.parametrize("estado,vigente", [("en_revision", True), ("aprobado", True),
                                            ("rechazado", True), ("borrador", False)])
def test_version_no_editable_409_en_todas_las_escrituras(cliente, token, mundo, estado, vigente):
    mundo.version.update(status=estado, is_current=vigente)
    cabecera = token()
    for r in (cliente.post(BASE + "?format=json", headers=cabecera, **con_json(NUEVA)),
              cliente.delete(BASE + "/77?format=json", headers=cabecera),
              cliente.post(BASE + "/77/move?format=json", headers=cabecera, **con_json({"direction": "bajar"}))):
        assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"
    assert not mundo.llamadas
    # Listar sigue permitido y avisa que no es editable.
    assert cliente.get(BASE + "?format=json", headers=cabecera).get_json()["editable"] is False


def test_solo_dueno_o_admin_edita(cliente, token, mundo):
    mundo.version["owner_id"] = 99
    r = cliente.post(BASE + "?format=json", headers=token(), **con_json(NUEVA))
    assert r.status_code == 403
    r = cliente.delete(BASE + "/77?format=json", headers=token(("EPIDEMIOLOGO",)))
    assert r.status_code == 403
    r = cliente.post(BASE + "?format=json", headers=token(("ADMINISTRADOR",)), **con_json(NUEVA))
    assert r.status_code == 201


def test_quitar(cliente, token, mundo):
    r = cliente.delete(BASE + "/77?format=json", headers=token())
    assert r.status_code == 200 and r.get_json() == {"id": 77, "eliminada": True}
    assert mundo.llamadas[0][0] == "quita" and mundo.llamadas[0][3].user_id == 7
    mundo.resultado = (False, "Esa intervención ya no está en esta versión.")
    r = cliente.delete(BASE + "/5?format=json", headers=token())
    assert r.status_code == 404
    assert cliente.delete(BASE + "/77", headers=token()).mimetype == "application/problem+xml"


@pytest.mark.parametrize("entrada,canonica", [("subir", "subir"), ("bajar", "bajar"),
                                              ("up", "subir"), ("DOWN", "bajar")])
def test_mover(cliente, token, mundo, entrada, canonica):
    r = cliente.post(BASE + "/77/move?format=json", headers=token(), **con_json({"direction": entrada}))
    assert r.status_code == 200
    assert r.get_json() == {"id": 77, "direction": canonica, "movida": True}
    assert mundo.llamadas[0][3] == canonica and mundo.llamadas[0][4].user_id == 7


def test_mover_en_extremo_no_es_error_y_xml(cliente, token, mundo):
    mundo.resultado = (False, None)
    r = cliente.post(BASE + "/77/move", headers=token(), data=a_xml({"direction": "subir"}, "movimiento"),
                     content_type="application/xml")
    assert r.status_code == 200
    assert ET.fromstring(r.data).find("movida").text == "false"


def test_mover_direccion_invalida_422_y_no_existe_404(cliente, token, mundo):
    r = cliente.post(BASE + "/77/move?format=json", headers=token(), **con_json({"direction": "lado"}))
    assert r.status_code == 422
    mundo.resultado = (False, "Esa intervención ya no está en esta versión.")
    r = cliente.post(BASE + "/5/move?format=json", headers=token(), **con_json({"direction": "subir"}))
    assert r.status_code == 404


# --- costo -----------------------------------------------------------------

COSTO = {"unit_cost": 1500.0, "cost_source": "SSNL 2025", "cost_is_assumption": False}


def test_costo_audita_en_la_misma_transaccion(cliente, token, mundo):
    r = cliente.put(BASE + "/77/cost?format=json", headers=token(("EPIDEMIOLOGO",)), **con_json(COSTO))
    assert r.status_code == 200
    assert r.get_json() == {"id": 77, "intervention_type_id": 2, "unit_cost": 1500.0,
                            "cost_source": "SSNL 2025", "cost_is_assumption": False}
    assert [s[0].split()[0] for s in mundo.sentencias] == ["SELECT", "UPDATE"]
    assert mundo.commits == 1
    contexto, accion, tipo, entidad, antes, despues, cur = mundo.auditoria[0]
    assert (accion, tipo, entidad, contexto.user_id) == ("UPDATE", "intervention_types", 2, 7)
    assert antes == {"unit_cost": 100, "cost_source": "viejo", "cost_is_assumption": True}
    assert despues["unit_cost"] == 1500.0 and cur is not None


def test_costo_en_version_aprobada_se_permite_y_xml(cliente, token, mundo):
    mundo.version["status"] = "aprobado"
    r = cliente.put(BASE + "/77/cost", headers=token(("ADMINISTRADOR",)),
                    data=a_xml(COSTO, "costo"), content_type="application/xml")
    assert r.status_code == 200 and r.mimetype == "application/xml"
    assert len(mundo.auditoria) == 1


def test_costo_analista_403(cliente, token, mundo):
    r = cliente.put(BASE + "/77/cost?format=json", headers=token(("ANALISTA",)), **con_json(COSTO))
    assert r.status_code == 403 and not mundo.sentencias


@pytest.mark.parametrize("cuerpo", [
    {"cost_source": "x"}, {"unit_cost": -1, "cost_source": "x"}, {"unit_cost": "abc", "cost_source": "x"},
    {"unit_cost": True}, {"unit_cost": 10}, {"unit_cost": 10, "cost_source": "x", "otro": 1},
    {"unit_cost": 10, "cost_is_assumption": "quizá"}])
def test_costo_invalido_422(cliente, token, mundo, cuerpo):
    r = cliente.put(BASE + "/77/cost?format=json", headers=token(("EPIDEMIOLOGO",)), **con_json(cuerpo))
    assert r.status_code == 422
    assert not mundo.sentencias and not mundo.auditoria


def test_costo_como_supuesto_sin_fuente_y_404(cliente, token, mundo):
    r = cliente.put(BASE + "/77/cost?format=json", headers=token(("EPIDEMIOLOGO",)),
                    **con_json({"unit_cost": 10, "cost_is_assumption": True}))
    assert r.status_code == 200
    r = cliente.put(BASE + "/5/cost?format=json", headers=token(("EPIDEMIOLOGO",)), **con_json(COSTO))
    assert r.status_code == 404
    assert len(mundo.auditoria) == 1 and mundo.commits == 1


def test_redis_caido_503(cliente, token, mundo, apagar_redis):
    cabecera = token()
    apagar_redis()
    assert cliente.get(BASE + "?format=json", headers=cabecera).status_code == 503


# --- contrato --------------------------------------------------------------

def _operaciones():
    contrato = json.loads((CONTRATO / "openapi.json").read_text(encoding="utf-8"))
    for metodos in contrato["paths"].values():
        for item in metodos.values():
            codigo = next(c for c in item["responses"] if c.startswith("2"))
            yield item["operationId"], item["responses"][codigo]["content"], item


def test_ejemplos_iguales_al_contrato_y_xml_generable():
    for op, contenido, item in _operaciones():
        en_json = json.loads((CONTRATO / "ejemplos" / (op + ".json")).read_text(encoding="utf-8"))
        en_xml = (CONTRATO / "ejemplos" / (op + ".xml")).read_text(encoding="utf-8")
        ET.fromstring(en_xml.encode("utf-8"))
        assert contenido["application/json"]["example"] == en_json
        assert contenido["application/xml"]["example"] == en_xml
        raiz = contenido["application/xml"]["schema"]["xml"]["name"]
        assert en_xml == (a_xml(en_json, raiz) + b"\n").decode("utf-8"), op
        if "requestBody" in item:
            peticion = json.loads((CONTRATO / "ejemplos" / (op + "_peticion.json")).read_text(encoding="utf-8"))
            assert item["requestBody"]["content"]["application/json"]["example"] == peticion
            assert (CONTRATO / "ejemplos" / (op + "_peticion.xml")).exists()


def test_openapi_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.status_code == 200 and r.data == (CONTRATO / "openapi.json").read_bytes()


def test_las_peticiones_de_ejemplo_se_aceptan(cliente, token, mundo):
    mundo.version["horizon_days"] = 120
    llamadas = (("agregar_intervencion", "post", BASE, 201, ("ANALISTA",)),
                ("mover_intervencion", "post", BASE + "/77/move", 200, ("ANALISTA",)),
                ("actualizar_costo_intervencion", "put", BASE + "/77/cost", 200, ("EPIDEMIOLOGO",)))
    for op, metodo, ruta, esperado, roles in llamadas:
        for ext, tipo in (("json", "application/json"), ("xml", "application/xml")):
            datos = (CONTRATO / "ejemplos" / ("%s_peticion.%s" % (op, ext))).read_bytes()
            mundo.filas = [dict(EXISTENTE)]
            r = getattr(cliente, metodo)(ruta + "?format=json", headers=token(roles), data=datos, content_type=tipo)
            assert r.status_code == esperado, (op, ext, r.data)
