from contextlib import contextmanager
from xml.etree import ElementTree as ET

import pytest

from backend_web import queries
from epidemia_comun import sesiones
from microservicios.roles import rutas

ROLES = {1: "ADMINISTRADOR", 2: "EPIDEMIOLOGO", 3: "ANALISTA"}


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
    monkeypatch.setattr(queries, "get_roles_catalogo",
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
        self.consultas = []

    def query(self, sql, params=(), one=False):
        sql = " ".join(sql.split())
        self.consultas.append((sql, params))
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
                 "data_after": None, "usuario": "Ana Analista"}]


@pytest.fixture
def bitacora_falsa(monkeypatch):
    falsa = Bitacora()
    monkeypatch.setattr(rutas, "query", falsa.query)
    return falsa


def test_bitacora_sin_filtros(cliente, admin, bitacora_falsa):
    r = cliente.get("/api/v1/audit?format=json", headers=admin)
    assert r.status_code == 200
    assert r.get_json() == {"total": 1, "eventos": [
        {"id": 912, "fecha": "2026-11-18T17:42:10+00:00", "usuario": "Ana Analista",
         "modulo": "users", "accion": "LOGIN", "entidad_id": "9", "datos": None, "ip": "10.0.0.15"}]}
    sql, params = bitacora_falsa.consultas[0]
    assert "WHERE" not in sql and params == (100,)


def test_bitacora_con_todos_los_filtros(cliente, admin, bitacora_falsa):
    cliente.get("/api/v1/audit?format=json&q=ana&user_id=9&module=simulation_run&action=RUN::fallido"
                "&limit=20", headers=admin)
    sql, params = bitacora_falsa.consultas[0]
    assert "a.action = 'RUN' AND a.data_after->>'estado' = %s" in sql
    assert params == ("%ana%", "%ana%", "%ana%", 9, "simulation_run", "fallido", 20)


def test_bitacora_con_una_accion_simple(cliente, admin, bitacora_falsa):
    cliente.get("/api/v1/audit?format=json&action=PERMISSION_DENIED", headers=admin)
    sql, params = bitacora_falsa.consultas[0]
    assert "a.action = %s" in sql and params == ("PERMISSION_DENIED", 100)


@pytest.mark.parametrize("consulta", ["limit=0", "limit=501", "limit=x", "user_id=-1"])
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


@pytest.mark.parametrize("ruta", ["/api/v1/audit", "/api/v1/audit/summary", "/api/v1/audit/filters"])
def test_la_bitacora_es_solo_del_administrador(cliente, token, bitacora_falsa, negados, ruta):
    assert cliente.get(ruta + "?format=json").status_code == 401
    r = cliente.get(ruta + "?format=json", headers=token(roles=("EPIDEMIOLOGO",)))
    assert r.status_code == 403 and bitacora_falsa.consultas == []
    assert negados[0][1:4] == ("PERMISSION_DENIED", "roles", ruta)


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
        "/api/v1/audit/filters"}
