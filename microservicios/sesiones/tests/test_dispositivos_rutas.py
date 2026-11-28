import pytest

from epidemia_comun import llaves
from microservicios.sesiones import almacen as sesiones, rutas
from microservicios.sesiones.tests.test_sesiones import login, token_servicio  # noqa: F401


DISP = "telefono-0001"


class Dispositivos:
    def __init__(self):
        self.llamadas = []
        self.autorizados = {7: (llaves.huella(DISP),), 1: ()}

    def registrar(self, contexto, usuario, identificador, etiqueta):
        self.llamadas.append((usuario, identificador, etiqueta))
        return {"id": 5, "user_id": usuario, "label": etiqueta, "status": "pendiente",
                "authorized_by": None, "authorized_at": None, "last_seen_at": None,
                "created_at": "2026-11-20T10:00:00+00:00"}

    def listar(self, usuario):
        self.llamadas.append(("listar", usuario))
        return []

    def autorizado(self, usuario, huella):
        return huella in self.autorizados.get(usuario, ())

    def cambiar(self, contexto, dispositivo, es_admin, estado, antes_de_guardar=None):
        self.llamadas.append((dispositivo, es_admin, estado))
        if dispositivo == 404:
            return None, "NO_ENCONTRADO"
        if dispositivo == 403:
            return None, "SOLO_ADMIN"
        return {"id": dispositivo, "status": estado}, None


@pytest.fixture
def falso(monkeypatch):
    f = Dispositivos()
    for nombre in ("registrar", "listar", "cambiar", "autorizado"):
        monkeypatch.setattr(rutas.dispositivos, nombre, getattr(f, nombre))
    return f


@pytest.fixture
def cliente(crear_cliente):
    return crear_cliente("sesiones")


def test_check_es_solo_de_servicios(cliente, falso, login):
    ruta = "/api/v1/sessions/devices/check?format=json"
    cuerpo = {"usuario": 7, "dispositivo_id": "telefono-0001", "etiqueta": " Mi cel "}
    assert cliente.post(ruta, json=cuerpo).status_code == 401
    persona, _ = login(roles=("ADMINISTRADOR",))
    assert cliente.post(ruta, json=cuerpo, headers=persona).status_code == 401
    r = cliente.post(ruta, json=cuerpo, headers=token_servicio(sub="auth"))
    assert r.status_code == 200 and r.get_json()["status"] == "pendiente"
    assert falso.llamadas == [(7, "telefono-0001", "Mi cel")]


@pytest.mark.parametrize("cuerpo", [{"usuario": 7}, {"usuario": 7, "dispositivo_id": "corto"},
                                    {"usuario": 0, "dispositivo_id": "telefono-0001"}])
def test_check_datos_invalidos_es_422(cliente, falso, cuerpo):
    r = cliente.post("/api/v1/sessions/devices/check?format=json", json=cuerpo, headers=token_servicio(sub="auth"))
    assert r.status_code == 422


def test_listar_los_propios_y_ajenos_solo_admin(cliente, falso, login):
    analista, _ = login(roles=("ANALISTA",))
    admin, _ = login(usuario=1, roles=("ADMINISTRADOR",))
    assert cliente.get("/api/v1/sessions/devices?format=json").status_code == 401
    assert cliente.get("/api/v1/sessions/devices?format=json", headers=analista).status_code == 200
    assert cliente.get("/api/v1/sessions/devices?user_id=8&format=json", headers=analista).status_code == 403
    assert cliente.get("/api/v1/sessions/devices?user_id=8&format=json", headers=admin).status_code == 200
    assert falso.llamadas == [("listar", 7), ("listar", 8)]


def test_autorizar_y_revocar_pasan_el_rol(cliente, falso, login):
    analista, _ = login(roles=("ANALISTA",), dispositivo=llaves.huella(DISP))
    admin, _ = login(usuario=1, roles=("ADMINISTRADOR",))
    assert cliente.post("/api/v1/sessions/devices/5/authorize?format=json").status_code == 401
    assert cliente.post("/api/v1/sessions/devices/5/authorize?format=json", headers=analista).get_json() == {"id": 5, "status": "autorizado"}
    assert cliente.post("/api/v1/sessions/devices/6/revoke?format=json", headers=admin).get_json() == {"id": 6, "status": "revocado"}
    assert falso.llamadas == [(5, False, "autorizado"), (6, True, "revocado")]


@pytest.mark.parametrize("dispositivo,estado,codigo", [(404, 404, "NO_ENCONTRADO"), (403, 403, "PERMISO_INSUFICIENTE")])
def test_errores_de_cambio(cliente, falso, login, dispositivo, estado, codigo):
    cabecera, _ = login(dispositivo=llaves.huella(DISP))
    r = cliente.post("/api/v1/sessions/devices/%d/authorize?format=json" % dispositivo, headers=cabecera)
    assert r.status_code == estado and r.get_json()["codigo"] == codigo


def test_id_invalido_es_422(cliente, falso, login):
    cabecera, _ = login(dispositivo=llaves.huella(DISP))
    assert cliente.post("/api/v1/sessions/devices/abc/revoke?format=json", headers=cabecera).status_code == 422


def test_cerrar_dispositivo_solo_cierra_sus_sesiones(redis_falso):
    h = llaves.huella("telefono-0001")
    a = sesiones.abrir(7, ["ANALISTA"], 600, dispositivo=h)
    b = sesiones.abrir(7, ["ANALISTA"], 600, dispositivo=llaves.huella("otro-0002"))
    c = sesiones.abrir(7, ["ANALISTA"], 600)
    assert sesiones.cerrar_dispositivo(7, h) == 1
    assert sesiones.obtener(a["sid"]) is None and sesiones.obtener(b["sid"]) and sesiones.obtener(c["sid"])


@pytest.mark.parametrize("accion", ["authorize", "revoke"])
def test_sin_dispositivo_autorizado_en_la_sesion_no_cambia_nada(cliente, falso, login, accion):
    ruta = "/api/v1/sessions/devices/5/%s?format=json" % accion
    sin_dispositivo, _ = login()
    ajeno, _ = login(dispositivo=llaves.huella("otro-dispositivo"))
    for cabecera in (sin_dispositivo, ajeno):
        r = cliente.post(ruta, headers=cabecera)
        assert r.status_code == 403 and r.get_json()["codigo"] == "DISPOSITIVO_NO_AUTORIZADO"
    admin, _ = login(usuario=1, roles=("ADMINISTRADOR",))
    assert cliente.post(ruta, headers=admin).status_code == 200
    assert [l for l in falso.llamadas if len(l) == 3] == [(5, True, "autorizado" if accion == "authorize" else "revocado")]
