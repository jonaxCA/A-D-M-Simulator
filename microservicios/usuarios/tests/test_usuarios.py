from contextlib import contextmanager
from xml.etree import ElementTree as ET

import psycopg2
import pytest

from backend_web import queries
from epidemia_comun import sesiones
from epidemia_comun.redis_compartido import RedisNoDisponible
from microservicios.usuarios import rutas


class BaseFalsa:
    """Solo la tabla users, con las sentencias que usa rutas.py."""

    def __init__(self):
        self.users = {7: [7, "admin", "admin@ejemplo.mx", "Admin", True],
                      9: [9, "ana", "ana@ejemplo.mx", "Ana Lista", True]}
        self.hashes = {}
        self.commits = 0

    def ejecutar(self, sql, p):
        if sql.startswith("SELECT id, username"):
            fila = self.users.get(p[0])
            return [tuple(fila)] if fila else []
        if sql.startswith("INSERT INTO users"):
            username, email, _, nombre, activo = p
            if any(u[1] == username.lower() for u in self.users.values()):
                raise psycopg2.errors.UniqueViolation("uq_users_username")
            nuevo = max(self.users) + 1
            self.users[nuevo] = [nuevo, username.lower(), email.lower(), nombre, activo]
            return [(nuevo,)]
        if sql.startswith("UPDATE users SET email"):
            self.users[p[3]][2:4] = [p[0].lower(), p[1]]
            if p[2]:
                self.hashes[p[3]] = p[2]
        elif sql.startswith("UPDATE users SET is_active"):
            self.users[p[1]][4] = p[0]
        elif sql.startswith("DELETE FROM users"):
            del self.users[p[0]]
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
    monkeypatch.setattr(rutas, "hash_password", lambda p: "hash-" + p)
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
    return crear_cliente("usuarios")


@pytest.fixture
def admin(token):
    return token(roles=("ADMINISTRADOR",))


def test_sin_token_401_y_sin_rol_403(cliente, token):
    assert cliente.get("/api/v1/users?format=json").status_code == 401
    r = cliente.get("/api/v1/users?format=json", headers=token(roles=("ANALISTA",)))
    assert r.status_code == 403


def test_lista_pasa_los_filtros(cliente, admin, monkeypatch):
    pedidos = []
    monkeypatch.setattr(queries, "get_usuarios_lista",
                        lambda **f: pedidos.append(f) or [{"id": 9, "nombre": "Ana Lista"}])
    r = cliente.get("/api/v1/users?format=json&q=ana&role_id=3&status=activo", headers=admin)
    assert r.status_code == 200 and r.get_json()["total"] == 1
    assert pedidos == [{"busqueda": "ana", "rol_id": 3, "estado": "activo"}]
    assert cliente.get("/api/v1/users?format=json&status=x", headers=admin).status_code == 422


def test_detalle_en_xml_con_roles(cliente, admin, monkeypatch):
    monkeypatch.setattr(queries, "get_usuario",
                        lambda i: {"id": i, "username": "ana", "role_id": 3} if i == 9 else None)
    monkeypatch.setattr(rutas, "get_user_roles", lambda i: ["ANALISTA"])
    r = cliente.get("/api/v1/users/9", headers=admin)
    assert r.content_type.startswith("application/xml")
    assert ET.fromstring(r.data).find("roles").findtext("item") == "ANALISTA"
    assert cliente.get("/api/v1/users/5?format=json", headers=admin).status_code == 404


def test_alta_audita_y_no_regresa_el_hash(cliente, admin, base, bitacora):
    r = cliente.post("/api/v1/users?format=json", headers=admin, json={
        "username": "Nuevo", "email": "Nuevo@Ejemplo.mx", "full_name": "Nuevo Usuario",
        "password": "contrasena-larga"})
    assert r.status_code == 201
    datos = r.get_json()
    assert datos["username"] == "nuevo" and "password_hash" not in datos
    assert base.commits == 1 and bitacora[0][0] == "CREATE"


def test_alta_acepta_xml(cliente, admin):
    cuerpo = ("<usuario><username>beto</username><email>beto@ejemplo.mx</email>"
              "<full_name>Beto</full_name><password>contrasena-larga</password>"
              "<is_active>false</is_active></usuario>")
    r = cliente.post("/api/v1/users", headers=admin, data=cuerpo, content_type="application/xml")
    assert r.status_code == 201
    assert ET.fromstring(r.data).findtext("is_active") == "false"


@pytest.mark.parametrize("cambio,estado", [
    ({"username": "ana"}, 409),
    ({"email": "no-es-correo"}, 422),
    ({"password": "corta"}, 422),
    ({"role_id": 1}, 422),
])
def test_alta_invalida(cliente, admin, cambio, estado):
    cuerpo = {"username": "otro", "email": "otro@ejemplo.mx", "full_name": "Otro",
              "password": "contrasena-larga", **cambio}
    r = cliente.post("/api/v1/users?format=json", headers=admin, json=cuerpo)
    assert r.status_code == estado


def test_editar_con_contrasena_cierra_sesiones(cliente, admin, base, bitacora):
    sesiones.abrir(9, ["ANALISTA"], ttl=600)
    r = cliente.put("/api/v1/users/9?format=json", headers=admin, json={
        "email": "ana2@ejemplo.mx", "full_name": "Ana", "password": "otra-contrasena"})
    assert r.status_code == 200
    assert r.get_json()["email"] == "ana2@ejemplo.mx" and r.get_json()["sesiones_cerradas"] == 1
    assert base.hashes[9] == "hash-otra-contrasena"
    assert bitacora[0][2]["email"] == "ana@ejemplo.mx"


def test_editar_no_cambia_username_ni_rol(cliente, admin):
    r = cliente.put("/api/v1/users/9?format=json", headers=admin,
                    json={"email": "a@ejemplo.mx", "full_name": "A", "username": "x"})
    assert r.status_code == 422


def test_desactivar_cierra_sesiones(cliente, admin, base, bitacora):
    sesiones.abrir(9, ["ANALISTA"], ttl=600)
    sesiones.abrir(9, ["ANALISTA"], ttl=600)
    r = cliente.post("/api/v1/users/9/deactivate?format=json", headers=admin)
    assert r.get_json() == {"id": 9, "is_active": False, "sesiones_cerradas": 2}
    assert base.users[9][4] is False and base.commits == 1
    assert bitacora[0][3]["is_active"] is False
    r = cliente.post("/api/v1/users/9/activate?format=json", headers=admin)
    assert r.get_json()["is_active"] is True


def test_desactivar_sin_redis_no_guarda(cliente, admin, base, monkeypatch):
    def caido(_):
        raise RedisNoDisponible("caído")
    monkeypatch.setattr(sesiones, "cerrar_todas", caido)
    r = cliente.post("/api/v1/users/9/deactivate?format=json", headers=admin)
    assert r.status_code == 503 and base.commits == 0


def test_no_puede_desactivarse_ni_borrarse_a_si_mismo(cliente, admin):
    assert cliente.post("/api/v1/users/7/deactivate?format=json", headers=admin).status_code == 409
    assert cliente.delete("/api/v1/users/7?format=json", headers=admin).status_code == 409


def test_eliminar_con_dependencias_es_409(cliente, admin, monkeypatch):
    monkeypatch.setattr(queries, "get_usuario", lambda i: {"id": i})
    monkeypatch.setattr(queries, "dependencias_usuario", lambda i: [("casos capturados", 4)])
    r = cliente.delete("/api/v1/users/9?format=json", headers=admin)
    assert r.status_code == 409 and "4 casos capturados" in r.get_json()["detail"]


def test_eliminar(cliente, admin, base, bitacora, monkeypatch):
    monkeypatch.setattr(queries, "get_usuario", lambda i: {"id": i})
    monkeypatch.setattr(queries, "dependencias_usuario", lambda i: [])
    r = cliente.delete("/api/v1/users/9?format=json", headers=admin)
    assert r.status_code == 200 and 9 not in base.users
    assert bitacora[0][0] == "DELETE"


def test_contrato_servido_es_el_de_docs(cliente):
    from microservicios.usuarios.app import CONTRATO
    r = cliente.get("/openapi.json")
    assert r.data == CONTRATO.read_bytes()
    assert set(r.get_json()["paths"]) == {
        "/api/v1/users", "/api/v1/users/{user_id}", "/api/v1/users/{user_id}/{accion}"}
