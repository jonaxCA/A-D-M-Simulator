"""Datos incompletos (D49): el aviso a quien capturó y la lista para el panel de la app."""
from xml.etree import ElementTree as ET

import pytest

from microservicios.casos import rutas
# base y bitacora son fixtures de test_casos: importarlas aquí las registra en este módulo.
from microservicios.casos.tests.test_casos import base, bitacora, cuerpo  # noqa: F401


@pytest.fixture
def avisos(monkeypatch):
    enviados = []

    class Resp:
        status_code = 201

    def llamar(servicio, metodo, ruta, **kw):
        enviados.append(kw["cuerpo"])
        return Resp()

    monkeypatch.setattr(rutas, "llamar", llamar)
    return enviados


@pytest.fixture
def cliente(crear_cliente, base, bitacora, avisos):
    return crear_cliente("casos")


@pytest.fixture
def captura(token):
    return token(roles=("CAPTURISTA",))


MINIMO = {"local_uuid": None, "device_id": None, "onset_date": None, "age": None, "sex": None,
          "latitude": None, "longitude": None, "test_result": None, "severity": None}


def test_que_le_falta_a_un_caso():
    assert rutas.faltantes({"age": None, "sex": "F", "onset_date": None, "test_result": "positivo",
                            "severity": None, "latitude": 25.6}) == ["edad", "inicio de síntomas", "gravedad"]
    assert rutas.faltantes(cuerpo()) == []


def test_un_caso_completo_no_avisa(cliente, captura, avisos):
    assert cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura).status_code == 201
    assert avisos == []


def test_un_caso_incompleto_avisa_a_quien_lo_capturo(cliente, captura, avisos):
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(age=None, latitude=None, longitude=None),
                     headers=captura)
    assert r.status_code == 201
    (aviso,) = avisos
    assert (aviso["user_id"], aviso["type"]) == (7, "DATA_INCOMPLETE")
    assert aviso["title"] == "El caso 1 tiene datos incompletos"
    assert aviso["body"] == "Falta: edad, ubicación. Complétalos si tienes el dato."
    assert aviso["payload"] == {"case_ids": [1], "faltantes": {"edad": 1, "ubicación": 1}}


def test_un_reintento_no_vuelve_a_avisar(cliente, captura, avisos):
    datos = cuerpo(age=None)
    cliente.post("/api/v1/cases?format=json", json=datos, headers=captura)
    assert cliente.post("/api/v1/cases?format=json", json=datos, headers=captura).status_code == 200
    assert len(avisos) == 1


def test_un_lote_da_un_solo_aviso(cliente, captura, avisos):
    casos = [cuerpo(local_uuid="%08d-1111-4111-8111-111111111111" % i, age=None, sex=None if i else "F")
             for i in range(3)] + [cuerpo(local_uuid="99999999-1111-4111-8111-111111111111")]
    r = cliente.post("/api/v1/cases/batch?format=json", json={"cases": casos}, headers=captura)
    assert [x["estado"] for x in r.get_json()["resultados"]] == [201] * 4
    (aviso,) = avisos
    assert aviso["title"] == "3 casos con datos incompletos"
    assert aviso["body"] == "Falta: edad (3), sexo (2). Complétalos si tienes el dato."


def test_si_notificaciones_falla_el_caso_se_queda(cliente, captura, monkeypatch, base):
    def falla(*a, **k):
        raise RuntimeError("caído")
    monkeypatch.setattr(rutas, "llamar", falla)
    assert cliente.post("/api/v1/cases?format=json", json=cuerpo(age=None), headers=captura).status_code == 201
    assert len(base.casos) == 1


def test_la_lista_de_incompletos_con_lo_que_falta(cliente, captura, base):
    cliente.post("/api/v1/cases?format=json", json=cuerpo(age=None), headers=captura)
    r = cliente.get("/api/v1/cases/incomplete?format=json", headers=captura)
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["casos"][0]["faltantes"] == ["edad"] and datos["total"] == 1
    sql, params = base.sentencias[-1]
    assert "c.age IS NULL" in sql and "c.latitude IS NULL" in sql
    assert "c.status IN ('pendiente', 'validado')" in sql
    # La capturista ve solo los suyos; la epidemióloga, todos.
    assert "c.reported_by = %s" in sql and params[0] == "7"


def test_la_epidemiologa_ve_los_de_todos(cliente, token, base):
    cliente.get("/api/v1/cases/incomplete?format=json", headers=token(roles=("EPIDEMIOLOGO",)))
    assert "c.reported_by = %s" not in base.sentencias[-1][0]


def test_incompletos_en_xml_y_paginacion(cliente, captura):
    raiz = ET.fromstring(cliente.get("/api/v1/cases/incomplete", headers=captura).data)
    assert raiz.tag == "casos_incompletos"
    assert cliente.get("/api/v1/cases/incomplete?per_page=101", headers=captura).status_code == 422
