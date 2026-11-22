from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from microservicios.notificaciones import almacen
from epidemia_comun.seguridad import token_servicio

RAIZ = Path(__file__).resolve().parents[3]
CREADA = datetime(2026, 10, 20, 15, tzinfo=timezone.utc)


class Bandeja:
    """La tabla notifications simulada, con las reglas de almacen.py."""

    def __init__(self):
        self.filas = {1: self.fila(1, 7), 2: self.fila(2, 8)}
        self.contextos = []
        self.a_rol = []

    @staticmethod
    def fila(notificacion_id, user_id):
        return {"id": notificacion_id, "user_id": user_id, "type": "RUN_FINISHED",
                "title": "La corrida SIM-00042 terminó", "body": "Ola Influenza ZMM, versión 2.",
                "payload": {"run_id": 42}, "read_at": None, "created_at": CREADA}

    def listar(self, user_id, solo_no_leidas=False, limite=50):
        filas = [dict(f) for f in self.filas.values() if f["user_id"] == user_id
                 and not (solo_no_leidas and f["read_at"])]
        return filas[:limite], sum(1 for f in filas if not f["read_at"])

    def marcar(self, notificacion_id, user_id, *, contexto):
        fila = self.filas.get(notificacion_id)
        if not fila or fila["user_id"] != user_id:
            return None, "No existe la notificación."
        fila["read_at"] = fila["read_at"] or CREADA
        self.contextos.append(contexto)
        return dict(fila), None

    def crear_a_rol(self, datos, rol, *, contexto):
        errores = almacen.valida_notificacion(datos, a_rol=True)
        if errores:
            return None, " ".join(errores)
        self.contextos.append(contexto)
        self.a_rol.append((rol, datos))
        return [10, 11], None

    def crear(self, datos, *, contexto):
        errores = almacen.valida_notificacion(datos)
        if errores:
            return None, " ".join(errores)
        if datos["user_id"] == 404:
            return None, "No existe el usuario destinatario."
        nuevo = max(self.filas) + 1
        self.filas[nuevo] = dict(self.fila(nuevo, datos["user_id"]), **datos)
        self.contextos.append(contexto)
        return nuevo, None


@pytest.fixture
def bandeja(monkeypatch):
    b = Bandeja()
    monkeypatch.setattr(almacen, "listar_notificaciones", b.listar)
    monkeypatch.setattr(almacen, "marcar_leida", b.marcar)
    monkeypatch.setattr(almacen, "crear_notificacion", b.crear)
    monkeypatch.setattr(almacen, "crear_notificaciones_a_rol", b.crear_a_rol)
    return b


@pytest.fixture
def cliente(crear_cliente, bandeja):
    return crear_cliente("notificaciones")


@pytest.fixture
def servicio(cliente):
    return {"Authorization": "Bearer " + token_servicio(cliente.application.config, "simulador")}


AVISO = {"user_id": 7, "type": "RUN_FAILED", "title": "La corrida SIM-00043 falló",
         "body": "Error forzado de prueba.", "payload": {"run_id": 43}}


# ---- leer -----------------------------------------------------------------------------

def test_sin_token_es_401(cliente):
    assert cliente.get("/api/v1/notifications").status_code == 401


@pytest.mark.parametrize("rol", ["CAPTURISTA", "ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR"])
def test_cada_quien_ve_solo_las_suyas(cliente, token, rol):
    datos = cliente.get("/api/v1/notifications?format=json", headers=token((rol,))).get_json()
    assert datos["total"] == 1 and datos["no_leidas"] == 1
    assert [n["id"] for n in datos["notificaciones"]] == [1]


def test_en_xml_cada_aviso_es_una_notificacion(cliente, token):
    r = cliente.get("/api/v1/notifications", headers=token())
    assert r.mimetype == "application/xml"
    assert [n.findtext("id") for n in ET.fromstring(r.data).findall("notificaciones/notificacion")] == ["1"]


@pytest.mark.parametrize("consulta", ["unread=si", "limit=0", "limit=201"])
def test_filtros_invalidos_son_422(cliente, token, consulta):
    assert cliente.get("/api/v1/notifications?" + consulta, headers=token()).status_code == 422


def test_marcar_leida_la_propia(cliente, token, bandeja):
    r = cliente.post("/api/v1/notifications/1/read?format=json", headers=token())
    assert r.status_code == 200 and r.get_json()["read_at"].startswith("2026-10-20")
    assert bandeja.contextos[0].user_id == 7
    datos = cliente.get("/api/v1/notifications?unread=true&format=json", headers=token()).get_json()
    assert datos["total"] == 0


def test_la_de_otra_persona_es_404(cliente, token, bandeja):
    assert cliente.post("/api/v1/notifications/2/read", headers=token()).status_code == 404
    assert bandeja.filas[2]["read_at"] is None


# ---- crear (ruta interna) -------------------------------------------------------------

def test_crear_con_token_de_servicio(cliente, servicio, bandeja):
    r = cliente.post("/api/v1/notifications?format=json", json=AVISO, headers=servicio)
    assert r.status_code == 201
    assert r.get_json() == {"id": 3, "user_id": 7, "type": "RUN_FAILED"}
    contexto = bandeja.contextos[0]
    assert contexto.user_id is None and contexto.user_agent == "servicio simulador"


@pytest.mark.parametrize("rol_destino,tipo", [("EPIDEMIOLOGO", "NEW_CASES"), ("ADMINISTRADOR", "SYSTEM")])
def test_crear_para_un_rol(cliente, servicio, bandeja, rol_destino, tipo):
    cuerpo = {k: v for k, v in AVISO.items() if k != "user_id"}
    r = cliente.post("/api/v1/notifications?format=json", json=dict(cuerpo, role=rol_destino, type=tipo),
                     headers=servicio)
    assert r.status_code == 201
    assert r.get_json() == {"role": rol_destino, "type": tipo, "total": 2}
    rol, datos = bandeja.a_rol[0]
    assert rol == rol_destino and "role" not in datos
    assert bandeja.contextos[0].user_agent == "servicio simulador"


@pytest.mark.parametrize("cuerpo", [dict(role="ANALISTA"), dict(role="EPIDEMIOLOGO", user_id=7)])
def test_rol_invalido_o_con_user_id_es_422(cliente, servicio, bandeja, cuerpo):
    base = {k: v for k, v in AVISO.items() if k != "user_id"}
    r = cliente.post("/api/v1/notifications?format=json", json=dict(base, **cuerpo), headers=servicio)
    assert r.status_code == 422 and bandeja.a_rol == []


@pytest.mark.parametrize("roles", [("ADMINISTRADOR",), ("ANALISTA",)])
def test_una_persona_no_crea_avisos(cliente, token, bandeja, roles):
    r = cliente.post("/api/v1/notifications?format=json", json=AVISO, headers=token(roles))
    assert r.status_code == 401
    assert len(bandeja.filas) == 2


def test_crear_en_xml(cliente, servicio):
    r = cliente.post("/api/v1/notifications", headers={**servicio, "Content-Type": "application/xml"},
                     data="<solicitud><user_id>7</user_id><type>SCENARIO_APPROVED</type>"
                          "<title>Versión 2 aprobada</title></solicitud>".encode("utf-8"))
    assert r.status_code == 201 and ET.fromstring(r.data).findtext("type") == "SCENARIO_APPROVED"


@pytest.mark.parametrize("cuerpo", [dict(AVISO, type="OTRO"), dict(AVISO, title=" "),
                                    dict(AVISO, payload=[1]), dict(AVISO, user_id="x"),
                                    dict(AVISO, entity_id=11)])
def test_aviso_invalido_es_422(cliente, servicio, cuerpo):
    r = cliente.post("/api/v1/notifications?format=json", json=cuerpo, headers=servicio)
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"


def test_destinatario_inexistente_es_404(cliente, servicio):
    r = cliente.post("/api/v1/notifications?format=json", json=dict(AVISO, user_id=404),
                     headers=servicio)
    assert r.status_code == 404


def test_redis_caido_es_503(cliente, token, apagar_redis):
    cabeceras = token()
    apagar_redis()
    assert cliente.get("/api/v1/notifications", headers=cabeceras).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/notificaciones/openapi.json").read_bytes()



# ------------------------------------------------------------------ preferencias (D49)

@pytest.fixture
def preferencias(monkeypatch, bandeja):
    """notification_preferences en memoria: {(user_id, tipo): prendido}."""
    guardadas = {}

    def query(sql, params=None, one=False):
        assert sql.startswith("SELECT type, enabled FROM notification_preferences")
        return [{"type": t, "enabled": e} for (u, t), e in guardadas.items() if u == params[0]]

    def guarda(user_id, cambios, *, contexto):
        guardadas.update({(user_id, t): v for t, v in cambios.items()})
    monkeypatch.setattr(almacen, "query", query)
    monkeypatch.setattr(almacen, "guarda_preferencias", guarda)
    return guardadas


def test_cada_perfil_ve_los_avisos_que_le_tocan(cliente, token, preferencias):
    for roles, tipos in ((("CAPTURISTA",), ["CASE_REJECTED", "CAMPAIGN", "DATA_INCOMPLETE"]),
                         (("EPIDEMIOLOGO",), ["SCENARIO_SUBMITTED", "NEW_CASES"]),
                         (("ADMINISTRADOR",), ["RUN_FINISHED", "RUN_FAILED", "SCENARIO_APPROVED",
                                               "SCENARIO_REJECTED", "SYSTEM"])):
        datos = cliente.get("/api/v1/notifications/preferences?format=json", headers=token(roles)).get_json()
        assert [p["type"] for p in datos["preferencias"]] == tipos, roles
        assert all(p["enabled"] for p in datos["preferencias"])
    admin = cliente.get("/api/v1/notifications/preferences?format=json",
                        headers=token(("ADMINISTRADOR",))).get_json()["preferencias"]
    assert [p["fijo"] for p in admin if p["type"] == "SYSTEM"] == [True]


def test_apagar_y_volver_a_prender(cliente, token, preferencias):
    cabeceras = token(("CAPTURISTA",))
    r = cliente.put("/api/v1/notifications/preferences?format=json", headers=cabeceras,
                    json={"CAMPAIGN": False, "DATA_INCOMPLETE": "false"})
    assert r.status_code == 200
    apagados = {p["type"] for p in r.get_json()["preferencias"] if not p["enabled"]}
    assert apagados == {"CAMPAIGN", "DATA_INCOMPLETE"} and preferencias[(7, "CAMPAIGN")] is False
    r = cliente.put("/api/v1/notifications/preferences?format=json", headers=cabeceras, json={"CAMPAIGN": True})
    assert {p["type"] for p in r.get_json()["preferencias"] if not p["enabled"]} == {"DATA_INCOMPLETE"}


@pytest.mark.parametrize("roles,cuerpo,mensaje", [
    (("ADMINISTRADOR",), {"SYSTEM": False}, "no se puede apagar"),
    (("CAPTURISTA",), {"NEW_CASES": False}, "no es un aviso que te llegue"),
    (("CAPTURISTA",), {"CAMPAIGN": "no"}, "true o false"),
    (("CAPTURISTA",), {}, "al menos un tipo"),
])
def test_preferencias_invalidas_son_422(cliente, token, preferencias, roles, cuerpo, mensaje):
    r = cliente.put("/api/v1/notifications/preferences?format=json", headers=token(roles), json=cuerpo)
    assert r.status_code == 422 and mensaje in r.get_json()["detail"]


def test_preferencias_en_xml(cliente, token, preferencias):
    raiz = ET.fromstring(cliente.get("/api/v1/notifications/preferences", headers=token(("CAPTURISTA",))).data)
    assert raiz.tag == "preferencias"
    assert raiz.find("preferencias/preferencia").findtext("type") == "CASE_REJECTED"


def test_un_aviso_apagado_no_se_crea(cliente, servicio, bandeja, monkeypatch):
    monkeypatch.setattr(almacen, "crear_notificacion", lambda datos, *, contexto: (None, None))
    r = cliente.post("/api/v1/notifications?format=json", json=AVISO, headers=servicio)
    assert r.status_code == 200
    assert r.get_json() == {"id": None, "user_id": 7, "type": "RUN_FAILED", "omitida": True}


def test_las_consultas_respetan_las_preferencias():
    """crear_notificacion y el aviso a un rol consultan notification_preferences."""
    import inspect
    assert "notification_preferences" in inspect.getsource(almacen.crear_notificacion)
    fuente = inspect.getsource(almacen.crear_notificaciones_a_rol)
    assert "NOT EXISTS" in fuente and "notification_preferences" in fuente
