"""Corregir un caso, cambiar su estado y su historial, con control de versión (D47, F7)."""
import json
from xml.etree import ElementTree as ET

import pytest

from microservicios.casos import rutas
# base y bitacora son fixtures de test_casos: importarlas aquí las registra en este módulo.
from microservicios.casos.tests.test_casos import base, bitacora, cuerpo  # noqa: F401

UUID_B = "7a2b3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d"


@pytest.fixture
def cliente(crear_cliente, base, bitacora):
    return crear_cliente("casos")


@pytest.fixture
def captura(token):
    return token(roles=("CAPTURISTA",))


@pytest.fixture
def epi(token):
    return token(roles=("EPIDEMIOLOGO",), sub="9")


@pytest.fixture
def avisos(monkeypatch):
    enviados = []

    class Resp:
        status_code = 201

    def llamar(servicio, metodo, ruta, **kw):
        enviados.append((servicio, ruta, kw["cuerpo"]))
        return Resp()

    monkeypatch.setattr(rutas, "llamar", llamar)
    return enviados


@pytest.fixture
def caso(cliente, captura):
    """Un caso capturado por la cuenta 7, en la versión 1."""
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura)
    assert r.status_code == 201
    return r.get_json()


def corrige(cliente, cabeceras, version, case_id=1, **campos):
    return cliente.patch("/api/v1/cases/%d?format=json" % case_id, json=campos,
                         headers=dict(cabeceras, **({"If-Match": version} if version else {})))


def estado(cliente, cabeceras, version, case_id=1, **campos):
    return cliente.post("/api/v1/cases/%d/status?format=json" % case_id, json=campos,
                        headers=dict(cabeceras, **({"If-Match": version} if version else {})))


# ---------------------------------------------------------------- versión y ETag

def test_un_caso_nuevo_va_en_la_version_1_con_su_etag(cliente, captura, caso):
    assert (caso["version"], caso["updated_at"], caso["status_reason"], caso["duplicate_of"]) == \
        (1, None, None, None)
    r = cliente.get("/api/v1/cases/1?format=json", headers=captura)
    assert r.headers["ETag"] == '"1"'


@pytest.mark.parametrize("version", ['"1"', "1", 'W/"1"'])
def test_if_match_acepta_la_version_con_y_sin_comillas(cliente, captura, caso, version):
    assert corrige(cliente, captura, version, age=35).status_code == 200


def test_sin_if_match_es_428(cliente, captura, caso):
    r = corrige(cliente, captura, None, age=35)
    assert r.status_code == 428 and "If-Match" in r.get_json()["detail"]


def test_if_match_que_no_es_version_es_422(cliente, captura, caso):
    assert corrige(cliente, captura, "abc", age=35).status_code == 422


# ---------------------------------------------------------------- corrección

def test_corregir_sube_la_version_y_deja_historial(cliente, captura, caso, base, bitacora):
    r = corrige(cliente, captura, '"1"', age=35, severity="grave", reason="Edad mal capturada")
    assert r.status_code == 200 and r.headers["ETag"] == '"2"'
    nuevo = r.get_json()
    assert (nuevo["version"], nuevo["age"], nuevo["severity"], nuevo["updated_by"]) == (2, 35, "grave", 7)
    (cambio,) = base.historial
    assert (cambio["version"], cambio["action"], cambio["reason"]) == (2, "correccion", "Edad mal capturada")
    assert json.loads(cambio["changes"]) == {"age": {"antes": 34, "despues": 35},
                                             "severity": {"antes": "leve", "despues": "grave"}}
    assert bitacora[-1][1:4] == ("UPDATE", "cases", 1)


def test_corregir_con_una_version_vieja_es_412_y_no_toca_nada(cliente, captura, epi, caso, base):
    assert corrige(cliente, epi, '"1"', age=40).status_code == 200
    r = corrige(cliente, captura, '"1"', age=35)
    assert r.status_code == 412 and r.headers["ETag"] == '"2"'
    assert r.get_json()["codigo"] == "CONFLICTO" and "versión 1" in r.get_json()["detail"]
    assert base.casos[0]["age"] == 40 and len(base.historial) == 1


def test_corregir_sin_cambios_no_sube_la_version(cliente, captura, caso, base):
    r = corrige(cliente, captura, '"1"', age=34, latitude=25.6866)
    assert r.status_code == 200 and r.get_json()["version"] == 1 and base.historial == []


def test_la_correccion_se_valida_con_el_resto_del_caso(cliente, captura, caso):
    # El inicio de síntomas (2026-09-28) no puede quedar después de la nueva fecha de reporte.
    r = corrige(cliente, captura, '"1"', report_date="2026-09-20")
    assert r.status_code == 422 and "inicio de síntomas" in r.get_json()["detail"]


@pytest.mark.parametrize("campos", [{}, {"local_uuid": UUID_B}, {"reported_by": 3}, {"status": "validado"}])
def test_solo_se_corrigen_los_campos_del_caso(cliente, captura, caso, campos):
    assert corrige(cliente, captura, '"1"', **campos).status_code == 422


def test_el_capturista_no_corrige_casos_ajenos(cliente, token, caso):
    otro = token(roles=("CAPTURISTA",), sub="8")
    r = corrige(cliente, otro, '"1"', age=35)
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


def test_el_capturista_no_corrige_un_caso_ya_validado(cliente, captura, epi, caso, avisos):
    assert estado(cliente, epi, '"1"', status="validado").status_code == 200
    r = corrige(cliente, captura, '"2"', age=35)
    assert r.status_code == 403 and "pendientes" in r.get_json()["detail"]


def test_el_epidemiologo_corrige_uno_validado_pero_no_uno_descartado(cliente, epi, caso, avisos):
    assert estado(cliente, epi, '"1"', status="validado").status_code == 200
    assert corrige(cliente, epi, '"2"', age=36).status_code == 200
    assert estado(cliente, epi, '"3"', status="descartado", reason="Prueba falsa").status_code == 200
    r = corrige(cliente, epi, '"4"', age=37)
    assert r.status_code == 409 and "reábrelo" in r.get_json()["detail"]


@pytest.mark.parametrize("roles", [("ANALISTA",), ("ADMINISTRADOR",)])
def test_otros_roles_no_corrigen(cliente, token, caso, roles):
    assert corrige(cliente, token(roles=roles), '"1"', age=35).status_code == 403


def test_corregir_desde_un_dispositivo_revocado_es_409(cliente, captura, caso):
    assert corrige(cliente, captura, '"1"', age=35, device_id=4).status_code == 409


def test_la_correccion_guarda_el_dispositivo(cliente, captura, caso, base):
    assert corrige(cliente, captura, '"1"', age=35, device_id=3).status_code == 200
    assert base.historial[0]["device_id"] == 3


def test_corregir_un_caso_que_no_existe_es_404(cliente, captura):
    assert corrige(cliente, captura, '"1"', case_id=77, age=35).status_code == 404


def test_corregir_en_xml(cliente, captura, caso):
    r = cliente.patch("/api/v1/cases/1", data="<correccion_caso><age>35</age></correccion_caso>",
                      headers=dict(captura, **{"If-Match": '"1"', "Content-Type": "application/xml"}))
    assert r.status_code == 200 and ET.fromstring(r.data).findtext("version") == "2"


# ---------------------------------------------------------------- estado

def test_validar(cliente, epi, caso, base, avisos):
    r = estado(cliente, epi, '"1"', status="validado")
    assert r.status_code == 200 and r.headers["ETag"] == '"2"'
    assert (r.get_json()["status"], r.get_json()["updated_by"]) == ("validado", 9)
    assert base.historial[0]["action"] == "estado" and avisos == []


def test_descartar_pide_motivo_y_avisa_al_capturista(cliente, epi, caso, avisos):
    assert estado(cliente, epi, '"1"', status="descartado").status_code == 422
    r = estado(cliente, epi, '"1"', status="descartado", reason="Resultado negativo confirmado")
    assert r.status_code == 200 and r.get_json()["status_reason"] == "Resultado negativo confirmado"
    ((servicio, ruta, aviso),) = avisos
    assert (servicio, ruta) == ("notificaciones", "/api/v1/notifications")
    assert (aviso["user_id"], aviso["type"]) == (7, "CASE_REJECTED")
    assert aviso["title"] == "Tu caso 1 se descartó" and aviso["payload"]["version"] == 2


def test_marcar_duplicado_apunta_al_original(cliente, captura, epi, caso, base, avisos):
    cliente.post("/api/v1/cases?format=json", json=cuerpo(local_uuid=UUID_B), headers=captura)
    assert estado(cliente, epi, '"1"', case_id=2, status="duplicado", reason="Mismo paciente").status_code == 422
    r = estado(cliente, epi, '"1"', case_id=2, status="duplicado", reason="Mismo paciente", duplicate_of=1)
    assert r.status_code == 200 and r.get_json()["duplicate_of"] == 1
    assert avisos[0][2]["title"] == "Tu caso 2 se marcó como duplicado del 1"
    # Un duplicado no es el original de otro, ni un caso de sí mismo.
    cliente.post("/api/v1/cases?format=json", json=cuerpo(local_uuid="8b3c4d5e-6f7a-4b2c-9d3e-4f5a6b7c8d9e"),
                 headers=captura)
    assert estado(cliente, epi, '"1"', case_id=3, status="duplicado", reason="x", duplicate_of=2).status_code == 422
    assert estado(cliente, epi, '"1"', case_id=3, status="duplicado", reason="x", duplicate_of=3).status_code == 422
    assert estado(cliente, epi, '"1"', case_id=3, status="duplicado", reason="x", duplicate_of=99).status_code == 422


def test_reabrir_limpia_el_duplicado(cliente, captura, epi, caso, avisos):
    cliente.post("/api/v1/cases?format=json", json=cuerpo(local_uuid=UUID_B), headers=captura)
    estado(cliente, epi, '"1"', case_id=2, status="duplicado", reason="Mismo paciente", duplicate_of=1)
    assert estado(cliente, epi, '"2"', case_id=2, status="pendiente").status_code == 422
    r = estado(cliente, epi, '"2"', case_id=2, status="pendiente", reason="No era el mismo")
    assert r.status_code == 200
    assert (r.get_json()["status"], r.get_json()["duplicate_of"]) == ("pendiente", None)


@pytest.mark.parametrize("desde,hacia", [("descartado", "validado"), ("pendiente", "pendiente")])
def test_transicion_no_permitida_es_409(cliente, epi, caso, base, avisos, desde, hacia):
    base.casos[0]["status"] = desde
    r = estado(cliente, epi, '"1"', status=hacia, reason="x")
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"


def test_estado_con_version_vieja_es_412(cliente, epi, caso, avisos):
    estado(cliente, epi, '"1"', status="validado")
    assert estado(cliente, epi, '"1"', status="descartado", reason="x").status_code == 412


@pytest.mark.parametrize("roles", [("CAPTURISTA",), ("ANALISTA",), ("ADMINISTRADOR",)])
def test_solo_el_epidemiologo_cambia_el_estado(cliente, token, caso, roles):
    assert estado(cliente, token(roles=roles), '"1"', status="validado").status_code == 403


@pytest.mark.parametrize("campos", [{"status": "aprobado"}, {"status": "validado", "otro": 1},
                                    {"status": "validado", "duplicate_of": 1},
                                    {"status": "descartado", "reason": "x" * 501}])
def test_cambio_de_estado_invalido_es_422(cliente, epi, caso, campos):
    assert estado(cliente, epi, '"1"', **campos).status_code == 422


def test_si_notificaciones_falla_el_cambio_se_queda(cliente, epi, caso, base, monkeypatch):
    def falla(*a, **k):
        raise RuntimeError("notificaciones caído")
    monkeypatch.setattr(rutas, "llamar", falla)
    assert estado(cliente, epi, '"1"', status="descartado", reason="x").status_code == 200
    assert base.casos[0]["status"] == "descartado"


# ---------------------------------------------------------------- historial

def test_historial_del_mas_viejo_al_mas_nuevo(cliente, captura, epi, caso, avisos):
    corrige(cliente, captura, '"1"', age=35, reason="Edad")
    estado(cliente, epi, '"2"', status="validado")
    datos = cliente.get("/api/v1/cases/1/history?format=json", headers=captura).get_json()
    assert (datos["case_id"], datos["version"]) == (1, 3)
    assert [(c["version"], c["action"], c["changed_by"]) for c in datos["cambios"]] == [
        (2, "correccion", 7), (3, "estado", 9)]
    assert datos["cambios"][1]["changes"] == {"status": {"antes": "pendiente", "despues": "validado"}}


def test_historial_vacio_en_xml(cliente, captura, caso):
    raiz = ET.fromstring(cliente.get("/api/v1/cases/1/history", headers=captura).data)
    assert raiz.tag == "historial_caso" and raiz.findtext("version") == "1"
    assert raiz.find("cambios").findall("item") == []


def test_historial_de_un_caso_que_no_existe(cliente, captura):
    assert cliente.get("/api/v1/cases/77/history?format=json", headers=captura).status_code == 404


def test_el_xml_real_de_las_rutas_nuevas_cumple_el_xsd(cliente, captura, epi, caso, avisos):
    from microservicios.casos.tests.test_contrato_casos import XSD
    cabeceras = dict(captura, **{"If-Match": '"1"'})
    XSD.validate(cliente.patch("/api/v1/cases/1", json={"age": 35}, headers=cabeceras).data.decode("utf-8"))
    r = cliente.post("/api/v1/cases/1/status", json={"status": "descartado", "reason": "x"},
                     headers=dict(epi, **{"If-Match": '"2"'}))
    XSD.validate(r.data.decode("utf-8"))
    XSD.validate(cliente.get("/api/v1/cases/1/history", headers=captura).data.decode("utf-8"))
