import json
from contextlib import contextmanager
from pathlib import Path
from xml.etree import ElementTree as ET

import psycopg2
import pytest

from backend_web import queries
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import a_xml
from microservicios.escenarios import datos as bd
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


class BaseFalsa:
    """microservicios.escenarios.datos en memoria: lo nuevo de D54 (proyectos y archivado).
    Sus reglas con candados se prueban contra la base en test_escenarios_bd.py."""

    def __init__(self):
        self.escenarios_ = {12: {"id": 12, "project_id": None, "owner_id": 7, "disease_id": 3,
                                 "region_id": 5, "status": "borrador"}}
        self.proyectos_ = {}
        self.llamadas = []

    def escenarios(self, ids):
        return {i: dict(self.escenarios_[i]) for i in ids if i in self.escenarios_}

    def proyecto(self, project_id):
        p = self.proyectos_.get(project_id)
        if p is None:
            return None
        n = sum(e["project_id"] == project_id for e in self.escenarios_.values())
        return dict(p, n_escenarios=n, enfermedad="Influenza", region="Monterrey", autor="Ana")

    def proyectos(self, estado=None, busqueda=None, regiones=None):
        self.llamadas.append(("proyectos", estado, busqueda, regiones))
        return [self.proyecto(i) for i, p in sorted(self.proyectos_.items(), reverse=True)
                if (estado is None or p["status"] == estado)
                and (regiones is None or p["region_id"] in regiones)]

    def escenarios_de(self, project_id):
        return [{"id": e["id"], "name": "E", "status": e["status"], "owner_id": e["owner_id"],
                 "version_number": 1, "version_status": "borrador"}
                for e in self.escenarios_.values() if e["project_id"] == project_id]

    def crea_proyecto(self, valores, *, contexto):
        project_id = len(self.proyectos_) + 1
        self.proyectos_[project_id] = dict(
            valores, id=project_id, owner_id=contexto.user_id, status="activo",
            objective=valores.get("objective"), created_at="2026-11-23T10:00:00+00:00",
            updated_at="2026-11-23T10:00:00+00:00")
        self.llamadas.append(("crea_proyecto", valores, contexto))
        return project_id

    def cambia_proyecto(self, project_id, cambios, *, contexto):
        self.proyectos_[project_id].update(cambios)
        self.llamadas.append(("cambia_proyecto", project_id, cambios))

    def cambia_estado_proyecto(self, project_id, estado, *, contexto):
        self.proyectos_[project_id]["status"] = estado
        self.llamadas.append(("estado_proyecto", project_id, estado))

    def asigna_proyecto(self, scenario_id, project_id, *, contexto):
        escenario = self.escenarios_.setdefault(scenario_id, dict(self.escenarios_[12], id=scenario_id))
        escenario["project_id"] = project_id
        self.llamadas.append(("asigna", scenario_id, project_id))

    def archiva(self, scenario_id, archivar, *, contexto):
        self.escenarios_[scenario_id]["status"] = "archivado" if archivar else "borrador"
        self.llamadas.append(("archiva", scenario_id, archivar))

    def versiones(self, scenario_id):
        return [{"id": 31, "version_number": 1, "status": "borrador", "is_current": True,
                 "population_size": 100, "horizon_days": 90, "initial_infected": 5, "notes": None,
                 "created_at": "2026-09-20T15:30:00+00:00", "por_edad": False, "created_by": 7,
                 "autor": "Ana", "submitted_at": "2026-09-21T09:00:00+00:00", "reviewed_by": 9,
                 "revisor": "Eva", "reviewed_at": "2026-09-21T12:00:00+00:00",
                 "review_comment": "Falta la fuente del R0.", "devuelta": True,
                 "approval_sha256": None, "n_intervenciones": 0}]


@pytest.fixture
def base(monkeypatch):
    falsa = BaseFalsa()
    for nombre in ("escenarios", "proyecto", "proyectos", "escenarios_de", "crea_proyecto",
                   "cambia_proyecto", "cambia_estado_proyecto", "asigna_proyecto", "archiva",
                   "versiones"):
        monkeypatch.setattr(bd, nombre, getattr(falsa, nombre))
    return falsa


@pytest.fixture
def mundo(monkeypatch, base):
    espia = Espia()
    espia.base = base
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
    assert r.get_json() == {"id": 13, "version_number": 1, "status": "borrador", "project_id": None}
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


VERSION = {"id": 11, "scenario_id": 3, "version_number": 2, "status": "aprobado",
           "population_size": 200000, "horizon_days": 180, "initial_infected": 100,
           "created_at": "2026-10-18T16:00:00+00:00", "reviewed_at": None, "review_comment": None,
           "scenario_name": "Brote", "scenario_status": "borrador", "disease_name": "Influenza",
           "region_name": "Monterrey", "creado_por": "Ana Analista", "revisado_por": None}


@pytest.fixture
def versiones(monkeypatch):
    consultas = []

    def query(sql, params=(), one=False):
        consultas.append((" ".join(sql.split()), params))
        return [dict(VERSION, region_id=5)]
    monkeypatch.setattr(rutas, "query", query)
    return consultas


def test_versiones_de_todos_los_escenarios(cliente, token, versiones):
    r = cliente.get("/api/v1/scenarios/versions?format=json", headers=token(("EPIDEMIOLOGO",)))
    assert r.status_code == 200 and r.get_json() == {"total": 1, "versiones": [VERSION]}
    sql, params = versiones[0]
    assert "ORDER BY (sv.status = 'aprobado') DESC" in sql and params == (None, None)
    raiz = ET.fromstring(cliente.get("/api/v1/scenarios/versions", headers=token()).data)
    assert raiz.tag == "versiones" and raiz.findtext("total") == "1"


def test_versiones_filtradas_por_estado(cliente, token, versiones):
    cliente.get("/api/v1/scenarios/versions?format=json&status=en_revision", headers=token())
    assert versiones[0][1] == ("en_revision", "en_revision")
    r = cliente.get("/api/v1/scenarios/versions?format=json&status=vigente", headers=token())
    assert r.status_code == 422 and len(versiones) == 1


def test_versiones_con_candado(cliente, token, versiones):
    assert cliente.get("/api/v1/scenarios/versions?format=json").status_code == 401
    r = cliente.get("/api/v1/scenarios/versions?format=json", headers=token(("CAPTURISTA",)))
    assert r.status_code == 403 and versiones == []


def test_versiones_no_chocan_con_un_escenario(cliente, token, mundo, versiones):
    assert cliente.get("/api/v1/scenarios/versions?format=json", headers=token()).status_code == 200
    assert cliente.get("/api/v1/scenarios/99?format=json", headers=token()).status_code == 404


# --- proyectos (D54) ------------------------------------------------------------

PROYECTO = {"name": "Influenza en Monterrey", "objective": "Comparar medidas.", "disease_id": 3,
            "region_id": 5, "period_start": "2026-10-01", "period_end": "2027-03-31",
            "motores": ["seir-ref", "abm-ref"]}


def crea_proyecto(cliente, token, **cambios):
    return cliente.post("/api/v1/projects?format=json", headers=token(),
                        **con_json(dict(PROYECTO, **cambios)))


def test_crear_listar_y_consultar_un_proyecto(cliente, token, mundo):
    r = crea_proyecto(cliente, token)
    assert r.status_code == 201
    proyecto = r.get_json()
    assert (proyecto["id"], proyecto["status"], proyecto["motores"]) == (1, "activo", ["seir-ref", "abm-ref"])
    _, valores, contexto = [x for x in mundo.base.llamadas if x[0] == "crea_proyecto"][0]
    assert valores["engines"] == ["seir-ref", "abm-ref"] and contexto.user_id == 7
    assert str(valores["period_start"]) == "2026-10-01"
    lista = cliente.get("/api/v1/projects?format=json", headers=token()).get_json()
    assert lista["total"] == 1 and mundo.base.llamadas[-1] == ("proyectos", "activo", None, None)
    cliente.get("/api/v1/projects?status=todos&q=flu&format=json", headers=token())
    assert mundo.base.llamadas[-1] == ("proyectos", None, "flu", None)
    detalle = cliente.get("/api/v1/projects/1?format=json", headers=token()).get_json()
    assert detalle["escenarios"] == [] and detalle["n_escenarios"] == 0
    assert cliente.get("/api/v1/projects/9?format=json", headers=token()).status_code == 404
    assert ET.fromstring(cliente.get("/api/v1/projects", headers=token()).data).find(
        "proyectos/proyecto/motores/motor").text == "seir-ref"


@pytest.mark.parametrize("cambios,mensaje", [
    ({"motores": []}, "motores"), ({"motores": ["seir-ref", "seir-ref"]}, "motores"),
    ({"motores": ["sir"]}, "motores"), ({"period_end": "2026-09-01"}, "period_end"),
    ({"period_start": "ayer"}, "period_start"), ({"disease_id": 99}, "enfermedad"),
    ({"region_id": 99}, "región"), ({"name": "ab"}, "name"), ({"color": "rojo"}, "desconocidos")])
def test_un_proyecto_invalido_es_422(cliente, token, mundo, cambios, mensaje):
    r = crea_proyecto(cliente, token, **cambios)
    assert r.status_code == 422 and mensaje in r.get_json()["detail"]
    assert mundo.base.proyectos_ == {}


def test_faltan_campos_del_proyecto(cliente, token, mundo):
    r = cliente.post("/api/v1/projects?format=json", headers=token(), **con_json({"name": "Algo"}))
    assert r.status_code == 422 and "Faltan" in r.get_json()["detail"]
    assert cliente.get("/api/v1/projects?status=otro&format=json", headers=token()).status_code == 422


def test_solo_el_dueno_o_el_admin_cambian_y_archivan_un_proyecto(cliente, token, mundo):
    crea_proyecto(cliente, token)
    otro = token(sub="8")
    assert cliente.patch("/api/v1/projects/1?format=json", headers=otro,
                         **con_json({"name": "Otro nombre"})).status_code == 403
    assert cliente.post("/api/v1/projects/1/archive?format=json", headers=otro).status_code == 403
    r = cliente.patch("/api/v1/projects/1?format=json", headers=token(("ADMINISTRADOR",), sub="8"),
                      **con_json({"period_end": "2027-04-30"}))
    assert r.status_code == 200 and r.get_json()["period_end"] == "2027-04-30"
    r = cliente.patch("/api/v1/projects/1?format=json", headers=token(),
                      **con_json({"period_end": "2026-01-01"}))
    assert r.status_code == 422
    assert cliente.patch("/api/v1/projects/1?format=json", headers=token(), **con_json({})).status_code == 422
    r = cliente.post("/api/v1/projects/1/archive?format=json", headers=token())
    assert r.status_code == 200 and r.get_json()["status"] == "archivado"
    r = cliente.post("/api/v1/projects/1/restore?format=json", headers=token())
    assert r.status_code == 200 and r.get_json()["status"] == "activo"


def test_investigador_y_autoridad_leen_pero_no_escriben(cliente, token, mundo):
    crea_proyecto(cliente, token)
    for rol in ("INVESTIGADOR", "AUTORIDAD_SANITARIA"):
        lector = token((rol,))
        for ruta in ("/api/v1/projects", "/api/v1/projects/1", "/api/v1/scenarios",
                     "/api/v1/scenarios/12", "/api/v1/scenarios/12/versions"):
            assert cliente.get(ruta + "?format=json", headers=lector).status_code == 200, (rol, ruta)
        assert cliente.post("/api/v1/projects?format=json", headers=lector,
                            **con_json(PROYECTO)).status_code == 403
        assert cliente.post("/api/v1/scenarios/12/archive?format=json", headers=lector).status_code == 403
    assert cliente.get("/api/v1/projects?format=json", headers=token(("CAPTURISTA",))).status_code == 403


def test_el_alcance_por_region_filtra_y_niega(cliente, token, mundo, alcance_falso):
    crea_proyecto(cliente, token)
    alcance_falso["regiones"] = [9]
    cliente.get("/api/v1/projects?format=json", headers=token())
    assert mundo.base.llamadas[-1] == ("proyectos", "activo", None, [9])
    assert cliente.get("/api/v1/projects/1?format=json", headers=token()).status_code == 403
    assert crea_proyecto(cliente, token, name="Fuera").status_code == 403
    assert cliente.get("/api/v1/scenarios?format=json", headers=token()).get_json()["total"] == 0
    for ruta in ("/api/v1/scenarios/12", "/api/v1/scenarios/12/versions"):
        assert cliente.get(ruta + "?format=json", headers=token()).status_code == 403
    assert cliente.post("/api/v1/scenarios/12/archive?format=json", headers=token()).status_code == 403
    assert cliente.post("/api/v1/scenarios/12/versions?format=json", headers=token(),
                        **con_json({"notes": "x"})).status_code == 403


def test_meter_y_sacar_un_escenario_de_un_proyecto(cliente, token, mundo):
    crea_proyecto(cliente, token)
    r = cliente.put("/api/v1/scenarios/12/project?format=json", headers=token(), **con_json({"project_id": 1}))
    assert r.status_code == 200 and r.get_json() == {"scenario_id": 12, "project_id": 1}
    assert cliente.get("/api/v1/scenarios?project_id=1&format=json", headers=token()).get_json()["total"] == 1
    assert cliente.get("/api/v1/scenarios?project_id=2&format=json", headers=token()).get_json()["total"] == 0
    assert cliente.get("/api/v1/scenarios/12?format=json", headers=token()).get_json()["project_id"] == 1
    r = cliente.put("/api/v1/scenarios/12/project?format=json", headers=token(), **con_json({"project_id": None}))
    assert r.status_code == 200 and mundo.base.escenarios_[12]["project_id"] is None
    assert cliente.put("/api/v1/scenarios/12/project?format=json", headers=token(sub="8"),
                       **con_json({"project_id": 1})).status_code == 403
    assert cliente.put("/api/v1/scenarios/12/project?format=json", headers=token(),
                       **con_json({"project_id": 9})).status_code == 422
    assert cliente.put("/api/v1/scenarios/12/project?format=json", headers=token(),
                       **con_json({"proyecto": 1})).status_code == 422


def test_un_escenario_solo_entra_a_un_proyecto_activo_de_su_enfermedad_y_region(cliente, token, mundo):
    crea_proyecto(cliente, token)
    mundo.base.proyectos_[1]["disease_id"] = 4
    r = cliente.put("/api/v1/scenarios/12/project?format=json", headers=token(), **con_json({"project_id": 1}))
    assert r.status_code == 422 and "enfermedad" in r.get_json()["detail"]
    mundo.base.proyectos_[1].update(disease_id=3, status="archivado")
    r = cliente.put("/api/v1/scenarios/12/project?format=json", headers=token(), **con_json({"project_id": 1}))
    assert r.status_code == 409
    assert not [x for x in mundo.base.llamadas if x[0] == "asigna"]


def test_crear_un_escenario_dentro_de_un_proyecto(cliente, token, mundo):
    crea_proyecto(cliente, token)
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), **con_json(dict(ALTA, project_id=1)))
    assert r.status_code == 201 and r.get_json()["project_id"] == 1
    assert ("asigna", 13, 1) in mundo.base.llamadas
    mundo.base.proyectos_[1]["region_id"] = 6
    r = cliente.post("/api/v1/scenarios?format=json", headers=token(), **con_json(dict(ALTA, project_id=1)))
    assert r.status_code == 422
    assert len([x for x in mundo.llamadas if x[0] == "crea_escenario"]) == 1


def test_el_duplicado_se_queda_en_el_proyecto_activo(cliente, token, mundo):
    crea_proyecto(cliente, token)
    mundo.base.escenarios_[12]["project_id"] = 1
    r = cliente.post("/api/v1/scenarios/12/duplicate?format=json", headers=token(), **con_json({"name": "Copia"}))
    assert r.status_code == 201 and r.get_json()["project_id"] == 1
    mundo.base.proyectos_[1]["status"] = "archivado"
    mundo.resultado_dup = (True, None, 15)
    r = cliente.post("/api/v1/scenarios/12/duplicate?format=json", headers=token(), **con_json({"name": "Otra"}))
    assert r.status_code == 201 and r.get_json()["project_id"] is None


# --- archivado (RF-D12, D54) ------------------------------------------------------

def test_archivar_y_restaurar_un_escenario(cliente, token, mundo):
    assert cliente.post("/api/v1/scenarios/12/archive?format=json", headers=token(sub="8")).status_code == 403
    assert cliente.post("/api/v1/scenarios/99/archive?format=json", headers=token()).status_code == 404
    r = cliente.post("/api/v1/scenarios/12/archive?format=json", headers=token())
    assert r.status_code == 200 and r.get_json() == {"id": 12, "status": "archivado"}
    assert ("archiva", 12, True) in mundo.base.llamadas
    r = cliente.post("/api/v1/scenarios/12/restore?format=json", headers=token(("ADMINISTRADOR",), sub="8"))
    assert r.status_code == 200 and r.get_json()["status"] == "borrador"


def test_la_lista_oculta_los_archivados_y_el_detalle_no_es_editable(cliente, token, mundo, monkeypatch):
    fila = queries.get_escenarios()[0]
    monkeypatch.setattr(queries, "get_escenarios", lambda busqueda=None: [dict(fila, status="archivado")])
    assert cliente.get("/api/v1/scenarios?format=json", headers=token()).get_json()["total"] == 0
    r = cliente.get("/api/v1/scenarios?archived=true&format=json", headers=token())
    assert r.get_json()["total"] == 1
    assert cliente.get("/api/v1/scenarios?archived=quiza&format=json", headers=token()).status_code == 422
    mundo.detalle["escenario"]["status"] = "archivado"
    assert cliente.get("/api/v1/scenarios/12?format=json", headers=token()).get_json()["editable"] is False


@pytest.mark.parametrize("escenario,version,mensaje", [
    ("archivado", "borrador", "archivado"), ("borrador", "en_revision", "en revisión")])
def test_no_se_versiona_un_archivado_ni_con_la_vigente_en_revision(cliente, token, mundo, escenario,
                                                                  version, mensaje):
    mundo.detalle["escenario"]["status"] = escenario
    mundo.detalle["version"] = dict(VERSION, status=version)
    r = cliente.post("/api/v1/scenarios/12/versions?format=json", headers=token(), **con_json({"notes": "x"}))
    assert r.status_code == 409 and mensaje in r.get_json()["detail"]
    assert not [x for x in mundo.llamadas if x[0] == "crea_version"]


def test_el_historial_trae_los_responsables(cliente, token, mundo):
    version = cliente.get("/api/v1/scenarios/12/versions?format=json", headers=token()).get_json()["versiones"][0]
    assert (version["id"], version["autor"], version["revisor"], version["devuelta"]) == (31, "Ana", "Eva", True)
    contrato = json.loads((CONTRATO / "ejemplos/historial_versiones.json").read_text(encoding="utf-8"))
    assert set(version) == set(contrato["versiones"][0])


def test_las_peticiones_de_ejemplo_nuevas_se_aceptan(cliente, token, mundo):
    for ext, tipo in (("json", "application/json"), ("xml", "application/xml")):
        datos = (CONTRATO / "ejemplos" / ("crear_proyecto_peticion." + ext)).read_bytes()
        r = cliente.post("/api/v1/projects?format=json", headers=token(), data=datos, content_type=tipo)
        assert r.status_code == 201, (ext, r.data)
        mundo.base.proyectos_.clear()
    crea_proyecto(cliente, token)
    mundo.base.proyectos_[4] = dict(mundo.base.proyectos_[1], id=4)   # el de los ejemplos
    for op, metodo, ruta in (("cambiar_proyecto", "patch", "/api/v1/projects/1"),
                             ("mover_a_proyecto", "put", "/api/v1/scenarios/12/project")):
        for ext, tipo in (("json", "application/json"), ("xml", "application/xml")):
            datos = (CONTRATO / "ejemplos" / ("%s_peticion.%s" % (op, ext))).read_bytes()
            r = getattr(cliente, metodo)(ruta + "?format=json", headers=token(), data=datos, content_type=tipo)
            assert r.status_code == 200, (op, ext, r.data)


@pytest.mark.parametrize("ruta,ejemplo", [("/api/v1/projects/1", "consultar_proyecto"),
                                          ("/api/v1/projects", "listar_proyectos"),
                                          ("/api/v1/scenarios/12", "consultar_escenario"),
                                          ("/api/v1/scenarios", "listar_escenarios")])
def test_las_respuestas_traen_las_claves_del_contrato(cliente, token, mundo, ruta, ejemplo):
    crea_proyecto(cliente, token)
    real = cliente.get(ruta + "?format=json", headers=token()).get_json()
    contrato = json.loads((CONTRATO / "ejemplos" / (ejemplo + ".json")).read_text(encoding="utf-8"))
    for lista in ("proyectos", "escenarios"):
        if lista in contrato and contrato[lista] and real.get(lista):
            assert set(real[lista][0]) == set(contrato[lista][0]), lista
    assert set(real) == set(contrato) or ejemplo == "consultar_escenario"
