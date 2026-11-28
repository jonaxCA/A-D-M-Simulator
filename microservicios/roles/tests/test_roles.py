from contextlib import contextmanager
from xml.etree import ElementTree as ET

import pytest

from microservicios.sesiones import almacen as sesiones
from microservicios.roles import rutas

ROLES = {1: "ADMINISTRADOR", 2: "EPIDEMIOLOGO", 3: "ANALISTA"}


@pytest.fixture(autouse=True)
def _sesiones(sesiones_en_proceso):
    pass


class BaseFalsa:
    """users, roles y user_roles, con las sentencias que usa rutas.py."""

    def __init__(self):
        self.user_roles = {7: [1], 9: [3]}
        self.commits = 0

    def ejecutar(self, sql, p):
        if sql.startswith("SELECT 1 FROM users"):
            return [(1,)] if p[0] in self.user_roles else []
        if sql.startswith("SELECT code FROM roles"):
            return [(ROLES[p[0]],)] if p[0] in ROLES else []
        if sql.startswith("SELECT role_id FROM user_roles"):
            return [(r,) for r in sorted(self.user_roles[p[0]])]
        if sql.startswith("DELETE FROM user_roles"):
            self.user_roles[p[0]] = []
        elif sql.startswith("INSERT INTO user_roles"):
            self.user_roles[p[0]].append(p[1])
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

    def fetchall(self):
        return list(self.filas)


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
                        data_after=None, **_: eventos.append((accion, entity_id, data_before, data_after)))
    return eventos


@pytest.fixture
def cliente(crear_cliente, base, bitacora):
    return crear_cliente("roles")


@pytest.fixture
def admin(token):
    return token(roles=("ADMINISTRADOR",))


def test_sin_token_401_y_sin_rol_403(cliente, token):
    assert cliente.get("/api/v1/roles?format=json").status_code == 401
    r = cliente.get("/api/v1/roles?format=json", headers=token(roles=("EPIDEMIOLOGO",)))
    assert r.status_code == 403


def test_lista_en_xml(cliente, admin, monkeypatch):
    monkeypatch.setattr(rutas, "catalogo_roles",
                        lambda: [{"id": i, "code": c, "name": c.title()} for i, c in ROLES.items()])
    r = cliente.get("/api/v1/roles", headers=admin)
    assert r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "catalogo_roles" and raiz.findtext("total") == "3"


def test_permisos_de_un_rol(cliente, admin, monkeypatch):
    def query(sql, params, one=False):
        if one:
            return {"id": 3, "code": "ANALISTA", "name": "Analista"} if params[0] == 3 else None
        return [{"code": "cases.read", "resource": "cases", "action": "read", "description": None}]
    monkeypatch.setattr(rutas, "query", query)
    r = cliente.get("/api/v1/roles/3/permissions?format=json", headers=admin)
    assert r.status_code == 200 and r.get_json()["permisos"][0]["code"] == "cases.read"
    assert cliente.get("/api/v1/roles/99/permissions?format=json", headers=admin).status_code == 404


def test_asignar_cambia_el_rol_audita_y_cierra_sesiones(cliente, admin, base, bitacora):
    sesiones.abrir(9, ["ANALISTA"], ttl=600)
    r = cliente.put("/api/v1/roles/assignments/9?format=json", headers=admin, json={"role_id": 2})
    assert r.get_json() == {"user_id": 9, "role_id": 2, "sesiones_cerradas": 1}
    assert base.user_roles[9] == [2] and base.commits == 1
    assert bitacora == [("UPDATE", 9, {"role_ids": [3]}, {"role_ids": [2]})]


def test_asignar_acepta_xml(cliente, admin, base):
    r = cliente.put("/api/v1/roles/assignments/9", headers=admin,
                    data="<asignacion><role_id>2</role_id></asignacion>",
                    content_type="application/xml")
    assert r.status_code == 200 and base.user_roles[9] == [2]


def test_mismo_rol_no_escribe_ni_cierra(cliente, admin, base, bitacora):
    sesiones.abrir(9, ["ANALISTA"], ttl=600)
    r = cliente.put("/api/v1/roles/assignments/9?format=json", headers=admin, json={"role_id": 3})
    assert r.get_json()["sesiones_cerradas"] == 0 and bitacora == []


def test_no_puede_quitarse_su_propio_rol_de_administrador(cliente, admin, base):
    r = cliente.put("/api/v1/roles/assignments/7?format=json", headers=admin, json={"role_id": 3})
    assert r.status_code == 409 and base.user_roles[7] == [1]


@pytest.mark.parametrize("usuario,cuerpo,estado", [
    (5, {"role_id": 2}, 404),
    (9, {"role_id": 99}, 422),
    (9, {"role_id": "x"}, 422),
    (9, {}, 422),
    (9, {"role_id": 2, "otro": 1}, 422),
])
def test_asignacion_invalida(cliente, admin, base, usuario, cuerpo, estado):
    r = cliente.put("/api/v1/roles/assignments/%d?format=json" % usuario, headers=admin, json=cuerpo)
    assert r.status_code == estado and base.commits == 0


class Bitacora:
    """audit_log para las rutas de la bitácora: guarda cada consulta para revisar sus filtros."""

    def __init__(self):
        self.consultas, self.region_del_escenario = [], 19

    def query(self, sql, params=(), one=False):
        sql = " ".join(sql.split())
        if "user_scopes" in sql or "WITH RECURSIVE" in sql:
            return []
        if sql.startswith("SELECT region_id FROM scenarios") or " JOIN scenarios s " in sql:
            return {"region_id": self.region_del_escenario}
        self.consultas.append((sql, params))
        if one and "count(*) AS n" in sql:
            return {"n": 57}
        if one:
            return {"eventos_totales": 912, "criticas": 7, "fallidos": 3, "activos_24h": 4}
        if "DISTINCT entity_type" in sql:
            return [{"entity_type": "roles"}, {"entity_type": "users"}]
        if "DISTINCT action" in sql:
            return [{"action": "LOGIN"}, {"action": "PERMISSION_DENIED"}]
        if "AS etapa" in sql:
            return [{"etapa": "fallido"}]
        if "DISTINCT u.id" in sql:
            return [{"id": 9, "full_name": "Ana Analista"}]
        return [{"id": 912, "occurred_at": "2026-11-18T17:42:10+00:00", "action": "LOGIN",
                 "entity_type": "users", "entity_id": "9", "ip": "10.0.0.15",
                 "data_before": None, "data_after": None, "usuario": "Ana Analista",
                 "user_id": 9}]


@pytest.fixture
def bitacora_falsa(monkeypatch):
    falsa = Bitacora()
    monkeypatch.setattr(rutas, "query", falsa.query)
    return falsa


def test_bitacora_sin_filtros(cliente, admin, bitacora_falsa):
    r = cliente.get("/api/v1/audit?format=json", headers=admin)
    assert r.status_code == 200
    assert r.get_json() == {"total": 1, "coincidencias": 57, "limit": 100, "offset": 0, "eventos": [
        {"id": 912, "fecha": "2026-11-18T17:42:10+00:00", "usuario": "Ana Analista", "usuario_id": 9,
         "modulo": "users", "accion": "LOGIN", "entidad_id": "9", "antes": None, "datos": None,
         "ip": "10.0.0.15"}]}
    sql, params = bitacora_falsa.consultas[1]
    assert "WHERE" not in sql and params == (100, 0)


def test_bitacora_con_todos_los_filtros(cliente, admin, bitacora_falsa):
    cliente.get("/api/v1/audit?format=json&q=ana&user_id=9&module=simulation_run&action=RUN::fallido"
                "&limit=20", headers=admin)
    sql, params = bitacora_falsa.consultas[1]
    assert "a.action = 'RUN' AND a.data_after->>'estado' = %s" in sql
    assert params == ("%ana%", "%ana%", "%ana%", 9, "simulation_run", "fallido", 20, 0)
    assert bitacora_falsa.consultas[0][1] == params[:-2]


def test_bitacora_por_entidad_rango_y_pagina(cliente, admin, bitacora_falsa):
    r = cliente.get("/api/v1/audit?format=json&module=scenarios&entity_id=31"
                    "&from=2026-11-01&to=2026-11-18&limit=10&offset=20", headers=admin)
    assert r.status_code == 200 and (r.get_json()["limit"], r.get_json()["offset"]) == (10, 20)
    sql, params = bitacora_falsa.consultas[1]
    assert "a.entity_id = %s" in sql and "a.occurred_at >= %s" in sql and "a.occurred_at < %s" in sql
    assert params[:2] == ("scenarios", "31")
    assert params[2].isoformat() == "2026-11-01T00:00:00"
    assert params[3].isoformat() == "2026-11-19T00:00:00"
    assert params[4:] == (10, 20)


def test_bitacora_con_una_accion_simple(cliente, admin, bitacora_falsa):
    cliente.get("/api/v1/audit?format=json&action=PERMISSION_DENIED", headers=admin)
    sql, params = bitacora_falsa.consultas[1]
    assert "a.action = %s" in sql and params == ("PERMISSION_DENIED", 100, 0)


@pytest.mark.parametrize("consulta", ["limit=0", "limit=501", "limit=x", "user_id=-1", "offset=-1",
                                      "offset=x", "from=ayer", "to=2026-13-01",
                                      "from=2026-11-18&to=2026-11-01"])
def test_bitacora_con_filtros_invalidos_es_422(cliente, admin, bitacora_falsa, consulta):
    assert cliente.get("/api/v1/audit?format=json&" + consulta, headers=admin).status_code == 422
    assert bitacora_falsa.consultas == []


def test_resumen_y_filtros_de_la_bitacora(cliente, admin, bitacora_falsa):
    r = cliente.get("/api/v1/audit/summary?format=json", headers=admin)
    assert r.get_json() == {"eventos_totales": 912, "criticas": 7, "fallidos": 3, "activos_24h": 4}
    r = cliente.get("/api/v1/audit/filters?format=json", headers=admin)
    assert r.get_json() == {"modulos": ["roles", "users"],
                            "acciones": ["LOGIN", "PERMISSION_DENIED", "RUN::fallido"],
                            "usuarios": [{"id": 9, "full_name": "Ana Analista"}]}


@pytest.mark.parametrize("ruta", ["/api/v1/audit", "/api/v1/audit/summary", "/api/v1/audit/filters",
                                  "/api/v1/scopes/9"])
def test_la_bitacora_es_solo_del_administrador(cliente, token, bitacora_falsa, negados, ruta):
    assert cliente.get(ruta + "?format=json").status_code == 401
    r = cliente.get(ruta + "?format=json", headers=token(roles=("EPIDEMIOLOGO",)))
    assert r.status_code == 403 and bitacora_falsa.consultas == []
    assert negados[0][1:4] == ("PERMISSION_DENIED", "roles", ruta)


@pytest.mark.parametrize("rol", ["ADMINISTRADOR", "EPIDEMIOLOGO", "ANALISTA"])
def test_historial_de_un_escenario_sin_ip(cliente, token, bitacora_falsa, rol):
    r = cliente.get("/api/v1/audit/history/scenario_versions/31?format=json&limit=5",
                    headers=token(roles=(rol,)))
    assert r.status_code == 200 and "ip" not in r.get_json()["eventos"][0]
    sql, params = bitacora_falsa.consultas[1]
    assert params == ("scenario_versions", "31", 5, 0)


@pytest.mark.parametrize("entidad", ["scenarios", "scenario_versions", "scenario_interventions"])
def test_historial_con_alcance_regional(cliente, token, bitacora_falsa, monkeypatch, entidad):
    cuenta = {"nacional": False, "region_ids": [20], "regiones_cubiertas": [20, 21], "institution_ids": []}
    monkeypatch.setattr(rutas, "alcance", lambda user_id: cuenta)
    ruta = "/api/v1/audit/history/%s/3?format=json" % entidad
    r = cliente.get(ruta, headers=token(roles=("ANALISTA",)))
    assert r.status_code == 403 and bitacora_falsa.consultas == []
    bitacora_falsa.region_del_escenario = 21
    assert cliente.get(ruta, headers=token(roles=("ANALISTA",))).status_code == 200


def test_historial_con_alcance_solo_por_institucion_no_se_limita(cliente, token, bitacora_falsa, monkeypatch):
    cuenta = {"nacional": False, "region_ids": [], "regiones_cubiertas": [], "institution_ids": [1]}
    monkeypatch.setattr(rutas, "alcance", lambda user_id: cuenta)
    r = cliente.get("/api/v1/audit/history/scenarios/3?format=json", headers=token(roles=("ANALISTA",)))
    assert r.status_code == 200


@pytest.mark.parametrize("rol", ["CAPTURISTA", "INVESTIGADOR"])
def test_historial_negado_a_los_demas_roles(cliente, token, bitacora_falsa, negados, rol):
    ruta = "/api/v1/audit/history/scenarios/3"
    assert cliente.get(ruta + "?format=json").status_code == 401
    assert cliente.get(ruta + "?format=json", headers=token(roles=(rol,))).status_code == 403
    assert bitacora_falsa.consultas == [] and negados[0][1] == "PERMISSION_DENIED"


def test_historial_solo_de_entidades_de_escenarios(cliente, admin, bitacora_falsa):
    r = cliente.get("/api/v1/audit/history/users/9?format=json", headers=admin)
    assert r.status_code == 404 and bitacora_falsa.consultas == []


def test_bitacora_en_xml(cliente, admin, bitacora_falsa):
    raiz = ET.fromstring(cliente.get("/api/v1/audit", headers=admin).data)
    assert raiz.tag == "bitacora" and raiz.findtext("total") == "1"
    assert raiz.find("eventos/item/accion").text == "LOGIN"


def test_contrato_servido_es_el_de_docs(cliente):
    from microservicios.roles.app import CONTRATO
    r = cliente.get("/openapi.json")
    assert r.data == CONTRATO.read_bytes()
    assert set(r.get_json()["paths"]) == {
        "/api/v1/roles", "/api/v1/roles/{role_id}/permissions",
        "/api/v1/roles/assignments/{user_id}", "/api/v1/audit", "/api/v1/audit/summary",
        "/api/v1/audit/filters", "/api/v1/audit/history/{entity_type}/{entity_id}",
        "/api/v1/scopes/me", "/api/v1/scopes/{user_id}",
        "/api/v1/permissions/me", "/api/v1/audit/denied"}


class Alcances:
    """regions, institutions y user_scopes, con las consultas de alcance() y del PUT."""

    def __init__(self, base):
        self.base = base
        self.regiones = {19: None, 191: 19, 192: 19, 20: None}
        self.instituciones = {1, 2}
        base.user_roles.setdefault(9, [3])
        base.scopes = {9: {"region_ids": [], "institution_ids": []}}
        base.ejecutar_original = base.ejecutar
        base.ejecutar = self.ejecutar

    def ejecutar(self, sql, p):
        if sql.startswith("SELECT 1 FROM users WHERE id = %s FOR UPDATE"):
            return [(1,)] if p[0] in self.base.scopes else []
        if sql.startswith("SELECT count(*) FROM regions"):
            return [(len([i for i in p[0] if i in self.regiones]),)]
        if sql.startswith("SELECT count(*) FROM institutions"):
            return [(len([i for i in p[0] if i in self.instituciones]),)]
        if sql.startswith("SELECT region_id FROM user_scopes"):
            return [(i,) for i in self.base.scopes[p[0]]["region_ids"]]
        if sql.startswith("SELECT institution_id FROM user_scopes"):
            return [(i,) for i in self.base.scopes[p[0]]["institution_ids"]]
        if sql.startswith("DELETE FROM user_scopes"):
            self.base.scopes[p[0]] = {"region_ids": [], "institution_ids": []}
        elif sql.startswith("INSERT INTO user_scopes (user_id, region_id"):
            self.base.scopes[p[0]]["region_ids"].append(p[1])
        elif sql.startswith("INSERT INTO user_scopes (user_id, institution_id"):
            self.base.scopes[p[0]]["institution_ids"].append(p[1])
        return []

    def query(self, sql, params=(), one=False):
        sql = " ".join(sql.split())
        if sql.startswith("SELECT 1 FROM users"):
            return (1,) if params[0] in self.base.scopes else None
        if sql.startswith("WITH RECURSIVE"):
            return [{"id": i} for i, padre in sorted(self.regiones.items())
                    if i in params[0] or padre in params[0]]
        alcance = self.base.scopes.get(params[0], {"region_ids": [], "institution_ids": []})
        if sql.startswith("SELECT region_id"):
            return [{"region_id": i} for i in alcance["region_ids"]]
        if sql.startswith("SELECT institution_id"):
            return [{"institution_id": i} for i in alcance["institution_ids"]]


@pytest.fixture
def alcances(base, monkeypatch):
    falso = Alcances(base)
    monkeypatch.setattr(rutas, "query", falso.query)
    return falso


def test_sin_alcance_la_cuenta_es_nacional(cliente, admin, alcances):
    r = cliente.get("/api/v1/scopes/9?format=json", headers=admin)
    assert r.get_json() == {"user_id": 9, "nacional": True, "region_ids": [], "regiones_cubiertas": [],
                            "institution_ids": []}
    assert cliente.get("/api/v1/scopes/5?format=json", headers=admin).status_code == 404


def test_asignar_alcance_audita_y_expande_las_hijas(cliente, admin, base, bitacora, alcances):
    r = cliente.put("/api/v1/scopes/9?format=json", headers=admin,
                    json={"region_ids": [19], "institution_ids": [1]})
    assert r.status_code == 200
    assert r.get_json() == {"user_id": 9, "nacional": False, "region_ids": [19],
                            "regiones_cubiertas": [19, 191, 192], "institution_ids": [1]}
    assert base.commits == 1
    assert bitacora == [("UPDATE", 9, {"region_ids": [], "institution_ids": []},
                         {"region_ids": [19], "institution_ids": [1]})]
    r = cliente.put("/api/v1/scopes/9?format=json", headers=admin,
                    json={"region_ids": [19], "institution_ids": [1]})
    assert len(bitacora) == 1
    r = cliente.put("/api/v1/scopes/9?format=json", headers=admin, json={})
    assert r.get_json()["nacional"] is True and len(bitacora) == 2


def test_asignar_alcance_acepta_xml(cliente, admin, alcances):
    cuerpo = ("<alcance><region_ids><item tipo=\"numero\">19</item><item tipo=\"numero\">20</item></region_ids>"
              "<institution_ids/></alcance>")
    r = cliente.put("/api/v1/scopes/9", headers=admin, data=cuerpo, content_type="application/xml")
    assert r.status_code == 200
    assert ET.fromstring(r.data).findtext("nacional") == "false"
    assert alcances.base.scopes[9]["region_ids"] == [19, 20]


@pytest.mark.parametrize("usuario,cuerpo,estado", [
    (5, {"region_ids": [19]}, 404),
    (9, {"region_ids": [99]}, 422),
    (9, {"institution_ids": [99]}, 422),
    (9, {"region_ids": ["x"]}, 422),
    (9, {"region_ids": [0]}, 422),
    (9, {"otro": []}, 422),
])
def test_alcance_invalido_no_escribe(cliente, admin, base, alcances, usuario, cuerpo, estado):
    r = cliente.put("/api/v1/scopes/%d?format=json" % usuario, headers=admin, json=cuerpo)
    assert r.status_code == estado and base.commits == 0 and base.scopes[9]["region_ids"] == []


def test_el_alcance_se_asigna_solo_con_administrador(cliente, token, base, alcances, negados):
    r = cliente.put("/api/v1/scopes/9?format=json", headers=token(roles=("EPIDEMIOLOGO",)),
                    json={"region_ids": [19]})
    assert r.status_code == 403 and base.commits == 0
    assert negados[0][1:4] == ("PERMISSION_DENIED", "roles", "/api/v1/scopes/9")


@pytest.mark.parametrize("rol", ["CAPTURISTA", "ANALISTA", "INVESTIGADOR", "AUTORIDAD_SANITARIA"])
def test_cada_cuenta_consulta_su_propio_alcance(cliente, token, base, alcances, rol):
    base.scopes[12] = {"region_ids": [20], "institution_ids": []}
    assert cliente.get("/api/v1/scopes/me?format=json").status_code == 401
    r = cliente.get("/api/v1/scopes/me?format=json", headers=token(roles=(rol,), sub="12"))
    assert r.status_code == 200
    assert (r.get_json()["user_id"], r.get_json()["regiones_cubiertas"]) == (12, [20])
