import json
from contextlib import contextmanager
from pathlib import Path
from xml.etree import ElementTree as ET

import psycopg2
import pytest

from backend_web import queries
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import a_xml
from microservicios.escenarios import rutas

RAIZ = Path(__file__).resolve().parents[3]
CONTRATO = RAIZ / "docs/contratos/escenarios"

REGION = {"id": 5, "code": "NL_MTY", "name": "Monterrey", "level": "municipio",
          "population": 1142994, "grupos": None, "sin_edad": 0}
ENFERMEDAD = {"id": 3, "code": "FLU", "name": "Influenza", "simulable": True,
              "faltan": 0, "sin_fuente": 0, "supuestos": 0}
ALTA = {"name": "Brote en Monterrey", "description": "Base", "disease_id": 3, "region_id": 5,
        "population_size": 1000000, "horizon_days": 90, "initial_infected": 50}
VERSION = {"id": 31, "version_number": 2, "status": "borrador", "is_current": True,
           "population_size": 1000000, "horizon_days": 90, "initial_infected": 50,
           "notes": None, "created_at": "2026-09-22T10:05:00+00:00",
           "population_by_age": {"0-14": 10, "15+": 90}, "population_age_unknown": 0,
           "age_unknown_policy": None, "autor": "Ana", "revisor": None, "submitted_at": None,
           "reviewed_at": None, "review_comment": None}


def detalle(owner_id=7, version=VERSION):
    return {"escenario": {"id": 12, "name": "E", "description": None, "status": "borrador",
                          "owner_id": owner_id, "created_at": "2026-09-20T15:30:00+00:00",
                          "disease_id": 3, "enfermedad": "Influenza", "default_params": {},
                          "region_id": 5, "region": "Monterrey", "autor": "Ana"},
            "version": version,
            "intervenciones": [{"id": 77, "code": "CIERRE_ESCUELAS", "name": "Cierre",
                                "target_layer": "escuela", "start_day": 1, "end_day": None,
                                "coverage": 0.5, "compliance": None, "params": {}, "order_index": 0,
                                "param_schema": {}}],
            "editable": True}


class Espia:
    def __init__(self):
        self.llamadas = []


@pytest.fixture
def mundo(monkeypatch):
    espia = Espia()
    monkeypatch.setattr(queries, "get_regiones_para_escenario", lambda: [REGION])
    monkeypatch.setattr(queries, "get_enfermedades_para_escenario", lambda: [ENFERMEDAD])
    monkeypatch.setattr(queries, "get_escenarios", lambda busqueda=None: [{
        "id": 12, "name": "E", "description": None, "status": "borrador",
        "created_at": "2026-09-20T15:30:00+00:00", "enfermedad": "Influenza", "region": "Monterrey",
        "autor": "Ana", "version_number": 1, "version_status": "borrador", "population_size": 100,
        "horizon_days": 90, "initial_infected": 5, "por_edad": False,
        "population_by_age": None}])
    espia.detalle = detalle()
    monkeypatch.setattr(queries, "get_escenario_detalle",
                        lambda sid, numero=None: espia.detalle if sid == 12 else None)
    monkeypatch.setattr(queries, "get_versiones", lambda sid: [{
        "version_number": 1, "status": "borrador", "is_current": True, "population_size": 100,
        "horizon_days": 90, "initial_infected": 5, "notes": None,
        "created_at": "2026-09-20T15:30:00+00:00", "por_edad": False, "autor": "Ana",
        "n_intervenciones": 0}])
    # El motor real se prueba en backend_web; aquí solo importa el cableado.
    monkeypatch.setattr(queries, "validar_escenario", lambda esc: [])
    monkeypatch.setattr(queries, "query", lambda sql, params=(), one=False: {"default_params": {}})

    def crea(datos, *, contexto):
        espia.llamadas.append(("crea_escenario", datos, contexto))
        return espia.resultado_crea
    espia.resultado_crea = (True, None, 13)
    monkeypatch.setattr(queries, "crea_escenario", crea)

    def crea_v(sid, datos, *, contexto):
        espia.llamadas.append(("crea_version", sid, datos, contexto))
        return True, None, 3
    monkeypatch.setattr(queries, "crea_version", crea_v)

    def dup(sid, numero, nombre, *, contexto):
        espia.llamadas.append(("duplica", sid, numero, nombre, contexto))
        return espia.resultado_dup
    espia.resultado_dup = (True, None, 14)
    monkeypatch.setattr(queries, "duplica_escenario", dup)

    class Resp:
        status_code = 200

        def __init__(self, cuerpo):
            self.cuerpo = cuerpo

        def json(self):
            return self.cuerpo

    def llamar(servicio, metodo, ruta, formato="json", cuerpo=None, **kw):
        espia.llamadas.append(("llamar", servicio, metodo, ruta, cuerpo))
        if isinstance(espia.validacion, Exception):
            raise espia.validacion
        return espia.validacion
    espia.validacion = Resp({"valido": True, "errores": [], "avisos": []})
    espia.Resp = Resp
    monkeypatch.setattr(rutas, "llamar", llamar)
    return espia


@pytest.fixture
def cliente(crear_cliente):
    return crear_cliente("escenarios")


def con_json(cuerpo):
    return {"data": json.dumps(cuerpo), "content_type": "application/json"}


# --- seguridad -------------------------------------------------------------

@pytest.mark.parametrize("metodo,ruta", [
    ("get", "/api/v1/scenarios"), ("get", "/api/v1/scenarios/12"),
    ("get", "/api/v1/scenarios/12/versions"), ("post", "/api/v1/scenarios"),
    ("post", "/api/v1/scenarios/12/versions"), ("post", "/api/v1/scenarios/12/duplicate")])
def test_sin_token_401_y_rol_ajeno_403(cliente, token, mundo, metodo, ruta):
    r = getattr(cliente, metodo)(ruta + "?format=json")
    assert r.status_code == 401 and r.get_json()["codigo"] == "TOKEN_AUSENTE"
    r = getattr(cliente, metodo)(ruta + "?format=json", headers=token(("OTRO",)))
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


# --- lectura ---------------------------------------------------------------

@pytest.mark.parametrize("rol", ["ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR"])
def test_listado_en_json_y_xml(cliente, token, mundo, rol):
    r = cliente.get("/api/v1/scenarios?format=json", headers=token((rol,)))
    assert r.status_code == 200 and r.mimetype == "application/json"
    assert r.get_json()["escenarios"][0]["id"] == 12
    assert "population_by_age" not in r.get_json()["escenarios"][0]
    r = cliente.get("/api/v1/scenarios", headers=token((rol,)))
    assert r.mimetype == "application/xml"
    assert ET.fromstring(r.data).find("escenarios/escenario/id").text == "12"
    r = cliente.get("/api/v1/scenarios", headers=dict(token((rol,)), Accept="application/json"))
    assert r.mimetype == "application/json"


def test_detalle_con_grupos_de_edad_como_lista(cliente, token, mundo):
    r = cliente.get("/api/v1/scenarios/12?format=json", headers=token())
    cuerpo = r.get_json()
    assert r.status_code == 200 and cuerpo["editable"] is True
    assert cuerpo["version"]["grupos_edad"] == [{"grupo": "0-14", "poblacion": 10},
                                                {"grupo": "15+", "poblacion": 90}]
    assert "param_schema" not in cuerpo["intervenciones"][0]
    # Sin claves como "0-14" como etiqueta XML, el XML se puede generar.
    assert cliente.get("/api/v1/scenarios/12", headers=token()).status_code == 200


def test_detalle_inexistente_404_y_version_invalida_422(cliente, token, mundo):
    r = cliente.get("/api/v1/scenarios/99?format=json", headers=token())
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"
    assert r.mimetype == "application/problem+json"
    r = cliente.get("/api/v1/scenarios/12?version=abc&format=json", headers=token())
    assert r.status_code == 422


def test_error_en_xml_por_defecto(cliente, token, mundo):
    r = cliente.get("/api/v1/scenarios/99", headers=token())
    assert r.status_code == 404 and r.mimetype == "application/problem+xml"


def test_historial(cliente, token, mundo):
    r = cliente.get("/api/v1/scenarios/12/versions?format=json", headers=token())
    assert r.status_code == 200 and r.get_json()["versiones"][0]["version_number"] == 1
    assert cliente.get("/api/v1/scenarios/99/versions", headers=token()).status_code == 404


def test_format_desconocido_400(cliente, token, mundo):
    assert cliente.get("/api/v1/scenarios?format=csv", headers=token()).status_code == 400


# --- alta ------------------------------------------------------------------

def test_crear_json_valida_con_servicio_y_guarda_con_contexto(cliente, token, mundo):
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), **con_json(ALTA))
    assert r.status_code == 201
    assert r.get_json() == {"id": 13, "version_number": 1, "status": "borrador"}
    llamada = [x for x in mundo.llamadas if x[0] == "llamar"][0]
    assert llamada[1:4] == ("validacion", "POST", "/api/v1/validate")
    assert llamada[4]["disease_id"] == "3"
    nombre, datos, contexto = [x for x in mundo.llamadas if x[0] == "crea_escenario"][0]
    assert datos["name"] == "Brote en Monterrey" and datos["population_size"] == 1000000
    assert contexto.user_id == 7  # la bitácora sale del token


def test_crear_acepta_xml(cliente, token, mundo):
    cuerpo = a_xml(dict(ALTA, stratify=False), "escenario")
    r = cliente.post("/api/v1/scenarios", headers=token(), data=cuerpo,
                     content_type="application/xml")
    assert r.status_code == 201 and r.mimetype == "application/xml"
    assert ET.fromstring(r.data).find("id").text == "13"
    datos = [x for x in mundo.llamadas if x[0] == "crea_escenario"][0][1]
    assert datos["horizon_days"] == 90 and datos["disease_id"] == 3


def test_crear_xml_malformado_400_y_tipo_415(cliente, token, mundo):
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), data="<a><b></a>",
                     content_type="application/xml")
    assert r.status_code == 400
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), data="x",
                     content_type="text/plain")
    assert r.status_code == 415


def test_crear_datos_invalidos_422(cliente, token, mundo):
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(),
                     **con_json(dict(ALTA, name="  ")))
    assert r.status_code == 422 and "nombre" in r.get_json()["detail"]
    assert not [x for x in mundo.llamadas if x[0] == "crea_escenario"]


def test_crear_campo_desconocido_y_booleano_invalido_422(cliente, token, mundo):
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), **con_json(dict(ALTA, owner_id=1)))
    assert r.status_code == 422
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), **con_json(dict(ALTA, stratify="tal vez")))
    assert r.status_code == 422


def test_validacion_rechaza_422(cliente, token, mundo):
    mundo.validacion = mundo.Resp({"valido": False, "errores": ["El motor rechaza el escenario: x"]})
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), **con_json(ALTA))
    assert r.status_code == 422 and "motor" in r.get_json()["detail"]
    assert not [x for x in mundo.llamadas if x[0] == "crea_escenario"]


def test_validacion_caida_503(cliente, token, mundo):
    mundo.validacion = ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio no respondió.")
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), **con_json(ALTA))
    assert r.status_code == 503 and r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
    assert not [x for x in mundo.llamadas if x[0] == "crea_escenario"]


def test_validacion_con_500_es_503(cliente, token, mundo):
    mundo.validacion.status_code = 500
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), **con_json(ALTA))
    assert r.status_code == 503


def test_crear_nombre_repetido_409(cliente, token, mundo):
    mundo.resultado_crea = (False, "Ya tienes un escenario con ese nombre. El nombre es único "
                                   "por autor, así que elige otro.", None)
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), **con_json(ALTA))
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"


def test_crea_escenario_real_audita_en_la_misma_transaccion(monkeypatch):
    """El alta del monolito: escenario, versión 1 y bitácora en un solo cursor."""
    eventos = []

    class Cur:
        n = 0

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, params=()):
            eventos.append(("sql", " ".join(sql.split())[:30]))

        def fetchone(self):
            Cur.n += 1
            return (100 + Cur.n,)

    class Conn:
        def cursor(self):
            return Cur()

        def commit(self):
            eventos.append(("commit",))

    @contextmanager
    def get_conn():
        yield Conn()

    def log_audit(contexto, accion, tipo, entidad, data_before=None, data_after=None, cur=None):
        assert isinstance(cur, Cur)
        eventos.append(("audit", accion, tipo, entidad))

    monkeypatch.setattr(queries, "get_conn", get_conn)
    monkeypatch.setattr(queries, "log_audit", log_audit)
    from backend_web.contexto import Contexto
    datos = {"name": "x", "description": None, "disease_id": 3, "region_id": 5,
             "population_size": 10, "horizon_days": 5, "initial_infected": 1,
             "population_by_age": None, "population_age_unknown": 0,
             "age_unknown_policy": None, "notes": None}
    assert queries.crea_escenario(datos, contexto=Contexto(7, None, "t")) == (True, None, 101)
    assert [e[0] for e in eventos] == ["sql", "sql", "audit", "commit"]
    assert eventos[2] == ("audit", "CREATE", "scenarios", 101)


# --- versiones -------------------------------------------------------------

VERSION_NUEVA = {"population_size": 2000, "horizon_days": 100, "initial_infected": 5,
                 "notes": "Más población."}


def test_nueva_version_dueno(cliente, token, mundo):
    r = cliente.post("/api/v1/scenarios/12/versions?format=json", headers=token(), **con_json(VERSION_NUEVA))
    assert r.status_code == 201
    assert r.get_json() == {"scenario_id": 12, "version_number": 3, "status": "borrador"}
    llamada = [x for x in mundo.llamadas if x[0] == "crea_version"][0]
    assert llamada[2]["notes"] == "Más población." and llamada[3].user_id == 7


def test_nueva_version_xml(cliente, token, mundo):
    r = cliente.post("/api/v1/scenarios/12/versions", headers=token(),
                     data=a_xml(VERSION_NUEVA, "version"), content_type="application/xml")
    assert r.status_code == 201 and r.mimetype == "application/xml"


def test_nueva_version_otro_usuario_403_pero_admin_si(cliente, token, mundo):
    mundo.detalle = detalle(owner_id=99)
    r = cliente.post("/api/v1/scenarios/12/versions?format=json", headers=token(), **con_json(VERSION_NUEVA))
    assert r.status_code == 403
    r = cliente.post("/api/v1/scenarios/12/versions?format=json",
                     headers=token(("ADMINISTRADOR",)), **con_json(VERSION_NUEVA))
    assert r.status_code == 201


def test_nueva_version_sin_comentario_422_y_404(cliente, token, mundo):
    r = cliente.post("/api/v1/scenarios/12/versions?format=json", headers=token(),
                     **con_json(dict(VERSION_NUEVA, notes="")))
    assert r.status_code == 422 and "comentario" in r.get_json()["detail"]
    r = cliente.post("/api/v1/scenarios/99/versions?format=json", headers=token(), **con_json(VERSION_NUEVA))
    assert r.status_code == 404


def test_nueva_version_concurrente_409(cliente, token, mundo, monkeypatch):
    monkeypatch.setattr(queries, "crea_version", lambda *a, **k: (
        False, "Otra persona creó una versión al mismo tiempo. Recarga.", None))
    r = cliente.post("/api/v1/scenarios/12/versions?format=json", headers=token(), **con_json(VERSION_NUEVA))
    assert r.status_code == 409


# --- duplicado -------------------------------------------------------------

def test_duplicar_no_exige_ser_dueno(cliente, token, mundo):
    mundo.detalle = detalle(owner_id=99)
    r = cliente.post("/api/v1/scenarios/12/duplicate?format=json", headers=token(),
                     **con_json({"name": "Copia", "version": 1}))
    assert r.status_code == 201
    assert r.get_json()["id"] == 14 and r.get_json()["version_origen"] == 1
    llamada = [x for x in mundo.llamadas if x[0] == "duplica"][0]
    assert llamada[1:4] == (12, 1, "Copia") and llamada[4].user_id == 7


def test_duplicar_usa_la_vigente_y_acepta_xml(cliente, token, mundo):
    r = cliente.post("/api/v1/scenarios/12/duplicate", headers=token(),
                     data=a_xml({"name": "Copia"}, "duplicado"), content_type="application/xml")
    assert r.status_code == 201
    assert [x for x in mundo.llamadas if x[0] == "duplica"][0][2] == 2


def test_duplicar_errores(cliente, token, mundo):
    r = cliente.post("/api/v1/scenarios/12/duplicate?format=json", headers=token(), **con_json({"name": " "}))
    assert r.status_code == 422
    r = cliente.post("/api/v1/scenarios/99/duplicate?format=json", headers=token(), **con_json({"name": "x"}))
    assert r.status_code == 404
    mundo.resultado_dup = (False, "Ya tienes un escenario con ese nombre. Elige otro.", None)
    r = cliente.post("/api/v1/scenarios/12/duplicate?format=json", headers=token(), **con_json({"name": "x"}))
    assert r.status_code == 409


def test_redis_caido_503(cliente, token, mundo, apagar_redis):
    cabecera = token()
    apagar_redis()
    assert cliente.get("/api/v1/scenarios?format=json", headers=cabecera).status_code == 503


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
    for op, ruta in (("crear_escenario", "/api/v1/scenarios"),
                     ("crear_version", "/api/v1/scenarios/12/versions"),
                     ("duplicar_escenario", "/api/v1/scenarios/12/duplicate")):
        for ext, tipo in (("json", "application/json"), ("xml", "application/xml")):
            datos = (CONTRATO / "ejemplos" / ("%s_peticion.%s" % (op, ext))).read_bytes()
            r = cliente.post(ruta + "?format=json", headers=token(), data=datos, content_type=tipo)
            assert r.status_code == 201, (op, ext, r.data)
