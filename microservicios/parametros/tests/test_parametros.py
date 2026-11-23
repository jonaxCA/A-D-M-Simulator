import json
from xml.etree import ElementTree as ET

import pytest

from epidemia_comun.errores import ErrorAPI
from microservicios.parametros import datos

COVID = {
    "r0": {"valor": 2.5, "fuente": "Liu et al. 2020", "supuesto": False},
    "incubacion_dias": {"valor": 5.1, "fuente": "Lauer et al. 2020", "supuesto": False},
    "letalidad_por_edad": {"0-19": 0.0001, "80+": 0.08},
}


class BaseFalsa:
    """microservicios.parametros.datos en memoria. El SQL de verdad se prueba contra la base en
    test_parametros_bd.py."""

    def __init__(self):
        self.params = {1: json.loads(json.dumps(COVID)),
                       2: {"r0": {"valor": 1.3, "fuente": "Biggerstaff et al. 2014", "supuesto": False}}}
        self.versiones_ = {1: [], 2: []}
        self.bitacora = []

    def parametros(self, disease_id):
        return self.params.get(disease_id)

    def guardar(self, disease_id, combinar, motivo, *, contexto):
        if disease_id not in self.params:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
        anteriores = self.params[disease_id]
        nuevos = combinar(anteriores)
        self.params[disease_id] = nuevos
        numero = len(self.versiones_[disease_id]) + 1
        self.versiones_[disease_id].append({"version": numero, "params": nuevos, "reason": motivo,
                                            "changed_by": contexto.user_id,
                                            "created_at": "2026-11-23T10:00:00+00:00"})
        self.bitacora.append((contexto.user_id, disease_id, anteriores, nuevos, motivo))
        return nuevos, numero

    def versiones(self, disease_id):
        return [{k: v for k, v in f.items() if k != "params"} for f in reversed(self.versiones_[disease_id])]

    def version(self, disease_id, numero):
        filas = [f for f in self.versiones_.get(disease_id, []) if f["version"] == numero]
        return dict(filas[0]) if filas else None


@pytest.fixture
def base(monkeypatch):
    falsa = BaseFalsa()
    for nombre in ("parametros", "guardar", "versiones", "version"):
        monkeypatch.setattr(datos, nombre, getattr(falsa, nombre))
    return falsa


@pytest.fixture
def bitacora(base):
    return base.bitacora


@pytest.fixture
def cliente(crear_cliente, base, bitacora):
    return crear_cliente("parametros")


@pytest.fixture
def epidemiologo(token):
    return token(roles=("EPIDEMIOLOGO",))


def test_consulta_xml_por_omision(cliente):
    r = cliente.get("/api/v1/diseases/2/parameters")
    assert r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "parametros"
    assert raiz.find("parametros").find("r0").findtext("valor") == "1.3"


def test_xml_valido_con_letalidad_por_edad(cliente):
    respuesta = cliente.get("/api/v1/diseases/1/parameters")
    assert respuesta.status_code == 200
    raiz = ET.fromstring(respuesta.data)
    assert raiz.find(".//entrada[@clave='0-19']").text == "0.0001"
    assert raiz.find(".//entrada[@clave='80+']").text == "0.08"


def test_consulta_json_con_format_y_con_accept(cliente):
    assert cliente.get("/api/v1/diseases/1/parameters?format=json").get_json()["parametros"]["r0"]["valor"] == 2.5
    r = cliente.get("/api/v1/diseases/1/parameters", headers={"Accept": "application/json"})
    assert r.content_type.startswith("application/json")


def test_format_invalido_es_400(cliente):
    assert cliente.get("/api/v1/diseases/1/parameters?format=csv").status_code == 400


def test_no_encontrada_es_404(cliente):
    assert cliente.get("/api/v1/diseases/9/parameters?format=json").status_code == 404
    assert cliente.get("/api/v1/diseases/9/parameters/status?format=json").status_code == 404


def test_estado_dice_que_falta_para_simular(cliente):
    datos = cliente.get("/api/v1/diseases/1/parameters/status?format=json").get_json()
    estados = {d["clave"]: d["estado"] for d in datos["detalle"]}
    assert estados["r0"] == "con_fuente" and estados["letalidad"] == "por_grupo"
    assert "infeccioso_dias" in datos["faltan"]


def test_escritura_sin_token_401_y_analista_403(cliente, token):
    cuerpo = {"parametros": {"r0": {"valor": 2.0, "supuesto": True}}}
    assert cliente.put("/api/v1/diseases/1/parameters?format=json", json=cuerpo).status_code == 401
    r = cliente.put("/api/v1/diseases/1/parameters?format=json", json=cuerpo,
                    headers=token(roles=("ANALISTA",)))
    assert r.status_code == 403


def test_guardar_con_fuente_conserva_lo_demas_y_audita(cliente, epidemiologo, base, bitacora):
    r = cliente.put("/api/v1/diseases/1/parameters?format=json", headers=epidemiologo, json={
        "parametros": {"infeccioso_dias": {"valor": 7, "fuente": "He et al. 2020"},
                       "tasa_hospitalizacion": {"valor": 0.04, "supuesto": True}}})
    assert r.status_code == 200
    guardados = base.params[1]
    assert guardados["infeccioso_dias"] == {"valor": 7, "fuente": "He et al. 2020", "supuesto": False}
    assert guardados["r0"] == COVID["r0"] and guardados["letalidad_por_edad"] == COVID["letalidad_por_edad"]
    assert r.get_json()["version"] == 1
    assert bitacora == [(7, 1, COVID, guardados, None)]


def test_cada_cambio_es_una_version_con_su_motivo(cliente, epidemiologo, base, token):
    for valor, motivo in ((1.9, None), (2.1, "Nueva revisión sistemática")):
        r = cliente.put("/api/v1/diseases/1/parameters?format=json", headers=epidemiologo,
                        json={"parametros": {"r0": {"valor": valor, "supuesto": True}}, "motivo": motivo})
        assert r.status_code == 200
    lista = cliente.get("/api/v1/diseases/1/parameters/versions?format=json").get_json()
    assert lista["total"] == 2 and [v["version"] for v in lista["versiones"]] == [2, 1]
    assert lista["versiones"][0]["reason"] == "Nueva revisión sistemática"
    uno = cliente.get("/api/v1/diseases/1/parameters/versions/1?format=json").get_json()
    assert uno["params"]["r0"]["valor"] == 1.9 and uno["disease_id"] == 1
    assert cliente.get("/api/v1/diseases/1/parameters/versions/9?format=json").status_code == 404
    assert cliente.get("/api/v1/diseases/1/parameters/versions/abc?format=json").status_code == 422
    assert cliente.get("/api/v1/diseases/9/parameters/versions?format=json").status_code == 404


def test_un_intervalo_se_guarda_y_sale_en_el_estado(cliente, epidemiologo, base):
    r = cliente.put("/api/v1/diseases/1/parameters?format=json", headers=epidemiologo, json={
        "parametros": {"r0": {"valor": 2.87, "fuente": "Billah 2020",
                              "intervalo": {"min": 2.39, "max": 3.44, "tipo": "IC95"}}}})
    assert r.status_code == 200
    detalle = cliente.get("/api/v1/diseases/1/parameters/status?format=json").get_json()["detalle"]
    r0 = [d for d in detalle if d["clave"] == "r0"][0]
    assert r0["intervalo"] == {"min": 2.39, "max": 3.44, "tipo": "IC95"}
    assert [d for d in detalle if d["clave"] == "letalidad"][0]["intervalo"] is None


def test_motivo_invalido_es_422(cliente, epidemiologo, base):
    for motivo in (5, "x" * 501):
        r = cliente.put("/api/v1/diseases/1/parameters?format=json", headers=epidemiologo,
                        json={"parametros": {"r0": {"valor": 2, "supuesto": True}}, "motivo": motivo})
        assert r.status_code == 422
    assert base.bitacora == []


def test_guardar_en_xml(cliente, epidemiologo, base):
    xml = (b"<solicitud><parametros><r0><valor>1.8</valor><fuente>Estudio NL</fuente>"
           b"<supuesto>false</supuesto></r0></parametros></solicitud>")
    r = cliente.put("/api/v1/diseases/1/parameters?format=json",
                    headers={**epidemiologo, "Content-Type": "application/xml"}, data=xml)
    assert r.status_code == 200
    assert base.params[1]["r0"] == {"valor": 1.8, "fuente": "Estudio NL", "supuesto": False}


@pytest.mark.parametrize("parametro", [
    {"valor": 2.0},
    {"valor": 2.0, "fuente": "   "},
    {"valor": 2.0, "supuesto": False},
])
def test_exige_fuente_o_marca_de_supuesto(cliente, epidemiologo, base, bitacora, parametro):
    r = cliente.put("/api/v1/diseases/1/parameters?format=json", headers=epidemiologo,
                    json={"parametros": {"r0": parametro}})
    assert r.status_code == 422 and "fuente o marcar supuesto" in r.get_json()["detail"]
    assert base.params[1] == COVID and bitacora == []


@pytest.mark.parametrize("cuerpo", [
    {"parametros": {"r0": {"valor": 25, "supuesto": True}}},
    {"parametros": {"inventado": {"valor": 1, "supuesto": True}}},
    {"parametros": {"tasa_hospitalizacion": {"valor": 4, "supuesto": True}}},
    {"parametros": {}, "name": "otro"},
    {"r0": {"valor": 2, "supuesto": True}},
])
def test_valores_invalidos_son_422(cliente, epidemiologo, cuerpo):
    r = cliente.put("/api/v1/diseases/1/parameters?format=json", headers=epidemiologo, json=cuerpo)
    assert r.status_code == 422


def test_guardar_en_inexistente_es_404(cliente, epidemiologo):
    r = cliente.put("/api/v1/diseases/9/parameters?format=json", headers=epidemiologo,
                    json={"parametros": {"r0": {"valor": 2, "supuesto": True}}})
    assert r.status_code == 404
