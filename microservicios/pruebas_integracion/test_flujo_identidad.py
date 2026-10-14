"""Pruebas de integración iniciales: el flujo de identidad entre auth, sesiones, usuarios y roles.

Los cuatro servicios comparten un solo Redis (fakeredis) y una sola base simulada en memoria,
así que lo que escribe uno lo ve el siguiente, como con los servicios desplegados.
"""
from contextlib import contextmanager

import pytest

from backend_web import auth as reglas_auth
from backend_web import queries
from microservicios.auth import rutas as rutas_auth
from microservicios.roles import rutas as rutas_roles
from microservicios.sesiones import rutas as rutas_sesiones
from microservicios.usuarios import rutas as rutas_usuarios

ROLES = {1: "ADMINISTRADOR", 2: "EPIDEMIOLOGO", 3: "ANALISTA"}


class Base:
    """users, roles y user_roles, con las sentencias que usan usuarios y roles."""

    def __init__(self):
        self.users = {7: [7, "admin", "admin@ejemplo.mx", "Admin", True],
                      9: [9, "ana", "ana@ejemplo.mx", "Ana Lista", True]}
        self.claves = {"admin": "clave-admin", "ana": "clave-ana"}
        self.user_roles = {7: [1], 9: [3]}

    def login(self, usuario, password):
        fila = next((u for u in self.users.values() if u[1] == usuario), None)
        if not fila or not fila[4] or self.claves.get(usuario) != password:
            return None, reglas_auth.MENSAJE_CREDENCIALES
        return {"id": fila[0], "username": fila[1], "full_name": fila[3],
                "roles": self.roles_de(fila[0])}, None

    def usuario(self, user_id):
        fila = self.users.get(user_id)
        return dict(zip(("id", "username", "email", "full_name", "is_active"), fila)) if fila else None

    def roles_de(self, user_id):
        return [ROLES[r] for r in self.user_roles[user_id]]

    def ejecutar(self, sql, p):
        if sql.startswith("SELECT id, username"):
            return [tuple(self.users[p[0]])] if p[0] in self.users else []
        if sql.startswith("UPDATE users SET is_active"):
            self.users[p[1]][4] = p[0]
        elif sql.startswith("SELECT 1 FROM users"):
            return [(1,)] if p[0] in self.users else []
        elif sql.startswith("SELECT code FROM roles"):
            return [(ROLES[p[0]],)] if p[0] in ROLES else []
        elif sql.startswith("SELECT role_id FROM user_roles"):
            return [(r,) for r in sorted(self.user_roles[p[0]])]
        elif sql.startswith("DELETE FROM user_roles"):
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
        pass


@pytest.fixture
def base(monkeypatch):
    falsa = Base()

    @contextmanager
    def get_conn():
        yield Conexion(falsa)

    for modulo in (rutas_usuarios, rutas_roles):
        monkeypatch.setattr(modulo, "get_conn", get_conn)
    monkeypatch.setattr(reglas_auth, "attempt_login", falsa.login)
    monkeypatch.setattr(queries, "get_usuario", falsa.usuario)
    monkeypatch.setattr(rutas_usuarios, "get_user_roles", falsa.roles_de)
    monkeypatch.setattr(queries, "get_roles_catalogo",
                        lambda: [{"id": i, "code": c, "name": c.title()} for i, c in ROLES.items()])
    return falsa


@pytest.fixture
def bitacora(monkeypatch):
    eventos = []
    for modulo in (rutas_auth, rutas_sesiones, rutas_usuarios, rutas_roles):
        monkeypatch.setattr(modulo, "log_audit",
                            lambda ctx, accion, entidad, entity_id=None, **_:
                            eventos.append((accion, str(entity_id))))
    return eventos


@pytest.fixture
def servicios(crear_cliente, base, bitacora):
    return {nombre: crear_cliente(nombre) for nombre in ("auth", "sesiones", "usuarios", "roles")}


def iniciar_sesion(servicios, usuario, password):
    auth = servicios["auth"]
    captcha = auth.get("/api/v1/auth/captcha?format=json").get_json()
    a, b = captcha["pregunta"].split(" + ")
    return auth.post("/api/v1/auth/login?format=json", json={
        "usuario": usuario, "password": password, "captcha_id": captcha["captcha_id"],
        "captcha_respuesta": str(int(a) + int(b))})


def bearer(respuesta):
    return {"Authorization": "Bearer " + respuesta.get_json()["access_token"]}


def actual(servicios, cabecera):
    return servicios["sesiones"].get("/api/v1/sessions/current?format=json", headers=cabecera)


def test_cambio_de_rol_y_baja_de_una_cuenta(servicios, base, bitacora):
    admin = bearer(iniciar_sesion(servicios, "admin", "clave-admin"))
    ana = bearer(iniciar_sesion(servicios, "ana", "clave-ana"))
    assert actual(servicios, ana).get_json()["roles"] == ["ANALISTA"]
    assert servicios["usuarios"].get("/api/v1/users/9?format=json", headers=ana).status_code == 403

    r = servicios["roles"].put("/api/v1/roles/assignments/9?format=json", headers=admin,
                               json={"role_id": 2})
    assert r.get_json()["sesiones_cerradas"] == 1
    assert actual(servicios, ana).status_code == 401

    ana = bearer(iniciar_sesion(servicios, "ana", "clave-ana"))
    assert actual(servicios, ana).get_json()["roles"] == ["EPIDEMIOLOGO"]

    r = servicios["usuarios"].post("/api/v1/users/9/deactivate?format=json", headers=admin)
    assert r.get_json() == {"id": 9, "is_active": False, "sesiones_cerradas": 1}
    assert actual(servicios, ana).status_code == 401
    assert iniciar_sesion(servicios, "ana", "clave-ana").status_code == 401
    assert actual(servicios, admin).status_code == 200

    assert [e[0] for e in bitacora] == ["LOGIN", "LOGIN", "UPDATE", "LOGIN", "UPDATE",
                                        "LOGIN_FAILED"]


def test_refresh_y_logout_valen_en_todos_los_servicios(servicios):
    login = iniciar_sesion(servicios, "admin", "clave-admin")
    viejo = bearer(login)

    r = servicios["sesiones"].post("/api/v1/sessions/refresh?format=json",
                                   json={"refresh_token": login.get_json()["refresh_token"]})
    assert r.status_code == 200
    nuevo = bearer(r)
    assert servicios["roles"].get("/api/v1/roles?format=json", headers=nuevo).status_code == 200
    assert servicios["usuarios"].get("/api/v1/users/9?format=json", headers=viejo).status_code == 200

    assert servicios["sesiones"].post("/api/v1/sessions/logout?format=json",
                                      headers=nuevo).status_code == 200
    for nombre, ruta in (("roles", "/api/v1/roles"), ("usuarios", "/api/v1/users/9")):
        for cabecera in (nuevo, viejo):
            r = servicios[nombre].get(ruta + "?format=json", headers=cabecera)
            assert r.status_code == 401 and r.get_json()["codigo"] == "TOKEN_REVOCADO"


def test_redis_caido_cierra_el_paso_en_todos(servicios, apagar_redis):
    admin = bearer(iniciar_sesion(servicios, "admin", "clave-admin"))
    apagar_redis()
    assert servicios["auth"].get("/api/v1/auth/captcha?format=json").status_code == 503
    for nombre, ruta in (("sesiones", "/api/v1/sessions/current"), ("roles", "/api/v1/roles"),
                         ("usuarios", "/api/v1/users/9")):
        assert servicios[nombre].get(ruta + "?format=json", headers=admin).status_code == 503
