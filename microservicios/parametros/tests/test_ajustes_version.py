"""Ajustes de los parámetros de una versión de escenario (D59). El SQL se prueba en test_parametros_bd.py."""
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import xmlschema

from epidemia_comun.errores import ErrorAPI
from microservicios.parametros import datos

RAIZ = Path(__file__).resolve().parents[3]
CATALOGO = {"r0": {"valor": 2.87, "fuente": "Billah et al. 2020", "supuesto": False},
            "incubacion_dias": {"valor": 5.1, "fuente": "Lauer et al. 2020", "supuesto": False}}
REGION = 9


def version(**cambios):
    fila = {"id": 11, "scenario_id": 3, "version_number": 2, "status": "borrador", "is_current": True,
            "disease_params": None, "param_overrides": {}, "owner_id": 7, "disease_id": 1,
            "region_id": REGION, "scenario_status": "activo", "default_params": CATALOGO}
    fila.update(cambios)
    return fila


class Base:
    def __init__(self):
        self.versiones = {11: version(), 12: version(id=12, status="en_revision", is_current=True,
                                                     disease_params=dict(CATALOGO), param_overrides={}),
                          13: version(id=13, scenario_status="archivado"), 14: version(id=14, owner_id=99),
                          15: version(id=15, is_current=False)}
        self.bitacora = []

    def version_de_escenario(self, version_id):
        fila = self.versiones.get(version_id)
        return json.loads(json.dumps(fila)) if fila else None

    def guardar_ajustes(self, version_id, exige_editable, combinar, *, contexto):
        fila = self.versiones.get(version_id)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la versión.")
        exige_editable(dict(fila))
        nuevos = combinar(fila["param_overrides"])
        self.bitacora.append((contexto.user_id, version_id, fila["param_overrides"], nuevos))
        fila["param_overrides"] = nuevos
        return nuevos


@pytest.fixture
def base(monkeypatch):
    falsa = Base()
    for nombre in ("version_de_escenario", "guardar_ajustes"):
        monkeypatch.setattr(datos, nombre, getattr(falsa, nombre))
    return falsa


@pytest.fixture
def cliente(crear_cliente, base):
    return crear_cliente("parametros")


R0_AJUSTADO = {"parametros": {"r0": {"valor": 3.2, "supuesto": True}}}


def poner(cliente, token, version_id=11, cuerpo=R0_AJUSTADO, roles=("ANALISTA",), **cambios):
    return cliente.put("/api/v1/versions/%d/parameters?format=json" % version_id, json=cuerpo,
                       headers=token(roles=roles, **cambios))


def test_un_borrador_sin_ajustes_usa_el_catalogo(cliente, token):
    r = cliente.get("/api/v1/versions/11/parameters?format=json", headers=token())
    datos_ = r.get_json()
    assert r.status_code == 200 and datos_["editable"] is True
    assert datos_["ajustes"] == {} and datos_["efectivos"] == CATALOGO and datos_["catalogo"] == CATALOGO
    assert datos_["estado"]["detalle"][0]["clave"] == "r0"


def test_ajustar_deja_el_catalogo_y_cambia_lo_efectivo(cliente, token, base):
    r = poner(cliente, token)
    assert r.status_code == 200
    cuerpo = r.get_json()
    assert cuerpo["ajustes"] == {"r0": {"valor": 3.2, "fuente": None, "supuesto": True}}
    assert cuerpo["efectivos"]["r0"]["valor"] == 3.2 and cuerpo["efectivos"]["incubacion_dias"]["valor"] == 5.1
    assert cuerpo["catalogo"]["r0"]["valor"] == 2.87
    assert base.bitacora == [(7, 11, {}, cuerpo["ajustes"])]
    r0 = next(d for d in cuerpo["estado"]["detalle"] if d["clave"] == "r0")
    assert r0["valor"] == 3.2 and r0["supuesto"] is True


def test_quitar_el_ajuste_vuelve_al_catalogo(cliente, token):
    poner(cliente, token)
    r = poner(cliente, token, cuerpo={"parametros": {"r0": None}})
    assert r.status_code == 200 and r.get_json()["ajustes"] == {}
    assert r.get_json()["efectivos"]["r0"]["valor"] == 2.87


def test_un_ajuste_lleva_fuente_o_supuesto_y_cabe_en_los_limites(cliente, token):
    assert poner(cliente, token, cuerpo={"parametros": {"r0": {"valor": 3.2}}}).status_code == 422
    assert poner(cliente, token, cuerpo={"parametros": {"r0": {"valor": 99, "supuesto": True}}}).status_code == 422
    assert poner(cliente, token, cuerpo={"parametros": {"nada": {"valor": 1, "supuesto": True}}}).status_code == 422
    assert poner(cliente, token, cuerpo={"otro": 1}).status_code == 422
    conintervalo = {"parametros": {"r0": {"valor": 3.2, "fuente": "Estudio propio",
                                          "intervalo": {"min": 2.8, "max": 3.6, "tipo": "IC95"}}}}
    r = poner(cliente, token, cuerpo=conintervalo)
    assert r.status_code == 200 and r.get_json()["ajustes"]["r0"]["intervalo"]["tipo"] == "IC95"


def test_una_version_enviada_se_lee_pero_no_se_ajusta(cliente, token):
    r = cliente.get("/api/v1/versions/12/parameters?format=json", headers=token())
    assert r.get_json()["editable"] is False and r.get_json()["efectivos"] == CATALOGO
    assert poner(cliente, token, 12).status_code == 409
    assert poner(cliente, token, 15).status_code == 409
    assert poner(cliente, token, 13).status_code == 409


def test_solo_su_dueno_o_un_administrador_ajusta(cliente, token):
    assert poner(cliente, token, 14).status_code == 403
    assert poner(cliente, token, 14, roles=("ADMINISTRADOR",)).status_code == 200


def test_el_investigador_lee_pero_no_ajusta_y_el_capturista_no_entra(cliente, token):
    assert cliente.get("/api/v1/versions/11/parameters", headers=token(("INVESTIGADOR",))).status_code == 200
    assert poner(cliente, token, roles=("INVESTIGADOR",)).status_code == 403
    assert cliente.get("/api/v1/versions/11/parameters", headers=token(("CAPTURISTA",))).status_code == 403
    assert cliente.get("/api/v1/versions/11/parameters").status_code == 401
    assert cliente.put("/api/v1/versions/11/parameters", json=R0_AJUSTADO).status_code == 401


def test_el_alcance_por_region_aplica(cliente, token, alcance_falso):
    alcance_falso["regiones"] = [REGION + 1]
    assert cliente.get("/api/v1/versions/11/parameters", headers=token()).status_code == 403
    assert poner(cliente, token).status_code == 403
    alcance_falso["regiones"] = [REGION]
    assert poner(cliente, token).status_code == 200


def test_una_version_inexistente_es_404(cliente, token):
    assert cliente.get("/api/v1/versions/99/parameters", headers=token()).status_code == 404
    assert poner(cliente, token, 99).status_code == 404


def test_las_respuestas_en_xml_validan_contra_el_xsd(cliente, token):
    xsd = xmlschema.XMLSchema(str(RAIZ / "docs/contratos/parametros/parametros.xsd"))
    cliente.put("/api/v1/versions/11/parameters", json=R0_AJUSTADO, headers=token())
    for r in (cliente.get("/api/v1/versions/11/parameters", headers=token()),
              cliente.get("/api/v1/versions/12/parameters", headers=token())):
        assert r.mimetype == "application/xml" and ET.fromstring(r.data).tag == "ajustes_version"
        xsd.validate(r.data.decode("utf-8"))
