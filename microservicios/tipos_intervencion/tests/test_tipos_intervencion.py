import json
from xml.etree import ElementTree as ET

import pytest

from epidemia_comun.errores import ErrorAPI
from microservicios.tipos_intervencion import datos

TIPOS = [
    {"id": 1, "code": "CIERRE_ESCUELAS", "name": "Cierre de escuelas",
     "description": "Desactiva la capa escuela.", "target_layer": "escuela",
     "primitive": "edge_modifier",
     "param_schema": {"type": "object", "required": ["reduccion"],
                      "properties": {"reduccion": {"type": "number", "minimum": 0, "maximum": 1}}},
     "unit_cost": None, "cost_unit": None, "cost_source": None, "cost_is_assumption": False},
    {"id": 2, "code": "CUBREBOCAS", "name": "Uso de cubrebocas", "description": None,
     "target_layer": "todas", "primitive": "edge_modifier",
     "param_schema": {"type": "object", "properties": {"eficacia": {"type": "number"}}},
     "unit_cost": 12.5, "cost_unit": "persona", "cost_source": "Supuesto", "cost_is_assumption": True},
]


class SupuestosFalsos:
    """tipos_intervencion.datos en memoria; su SQL se prueba contra la base en test_tipos_intervencion_bd.py."""

    def __init__(self):
        self.filas = {}          # (type_id, parametro, enfermedad) -> supuesto
        self.bitacora = []

    def efectividad(self, type_id):
        return [dict(f) for (t, _p, _e), f in sorted(self.filas.items(), key=lambda x: str(x[0]))
                if t == type_id]

    def enfermedad_id(self, codigo):
        return {"SARS_COV_2_ANCESTRAL": 1, "INFLUENZA_ESTACIONAL": 2}.get(codigo)

    def guarda_efectividad(self, type_id, parametro, disease_id, valores, *, contexto):
        clave = (type_id, parametro, disease_id)
        nuevo = clave not in self.filas
        codigo = {1: "SARS_COV_2_ANCESTRAL", 2: "INFLUENZA_ESTACIONAL"}.get(disease_id)
        self.filas[clave] = dict(valores, parametro=parametro, enfermedad=codigo, updated_by=contexto.user_id,
                                 updated_at="2026-11-23T10:00:00+00:00")
        self.bitacora.append((contexto.user_id, "CREATE" if nuevo else "UPDATE", clave))
        return nuevo

    def efectividad_de(self, type_id, parametro, disease_id):
        if (type_id, parametro, disease_id) not in self.filas:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe ese supuesto de efectividad.")
        return dict(self.filas[(type_id, parametro, disease_id)])


@pytest.fixture
def supuestos(monkeypatch):
    falsos = SupuestosFalsos()
    monkeypatch.setattr(datos, "tipos", lambda: [dict(t) for t in TIPOS])
    for nombre in ("efectividad", "enfermedad_id", "guarda_efectividad", "efectividad_de"):
        monkeypatch.setattr(datos, nombre, getattr(falsos, nombre))
    return falsos


@pytest.fixture
def cliente(crear_cliente, supuestos):
    return crear_cliente("tipos_intervencion")


def test_lista_en_json_sin_token(cliente):
    r = cliente.get("/api/v1/intervention-types?format=json")
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["total"] == 2
    assert datos["tipos"][0]["param_schema"]["required"] == ["reduccion"]


def test_lista_en_xml_por_omision(cliente):
    r = cliente.get("/api/v1/intervention-types")
    assert r.status_code == 200
    assert r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "catalogo_tipos_intervencion"
    assert [t.findtext("code") for t in raiz.find("tipos").findall("tipo")] == \
        ["CIERRE_ESCUELAS", "CUBREBOCAS"]


def test_detalle_por_codigo_sin_importar_mayusculas(cliente):
    r = cliente.get("/api/v1/intervention-types/cubrebocas",
                    headers={"Accept": "application/json"})
    assert r.status_code == 200
    assert r.get_json()["unit_cost"] == 12.5


@pytest.mark.parametrize("codigo", ["NO_EXISTE", "1ABC", "a-b", "X" * 60])
def test_codigo_desconocido_o_invalido_es_404(cliente, codigo):
    r = cliente.get("/api/v1/intervention-types/%s?format=json" % codigo)
    assert r.status_code == 404
    assert r.content_type.startswith("application/problem+json")
    assert json.loads(r.data)["codigo"] == "NO_ENCONTRADO"


def test_formato_desconocido_es_400(cliente):
    assert cliente.get("/api/v1/intervention-types?format=csv").status_code == 400



# ---- supuestos de efectividad (D56) -----------------------------------------------------------

SUPUESTO = {"parametro": "eficacia", "valor": 0.85, "min": 0.66, "max": 0.93,
            "fuente": "Chu et al. 2020, Lancet", "supuesto": True}


def test_el_detalle_trae_su_efectividad(cliente, supuestos, token):
    assert cliente.get("/api/v1/intervention-types/CUBREBOCAS?format=json").get_json()["efectividad"] == []
    cliente.put("/api/v1/intervention-types/cubrebocas/effectiveness?format=json",
                headers=token(("EPIDEMIOLOGO",)), json=SUPUESTO)
    detalle = cliente.get("/api/v1/intervention-types/CUBREBOCAS?format=json").get_json()
    assert detalle["efectividad"][0]["valor"] == 0.85
    lista = cliente.get("/api/v1/intervention-types/CUBREBOCAS/effectiveness?format=json").get_json()
    assert lista["total"] == 1 and lista["code"] == "CUBREBOCAS"
    raiz = ET.fromstring(cliente.get("/api/v1/intervention-types/CUBREBOCAS/effectiveness").data)
    assert raiz.find("efectividad/supuesto/parametro").text == "eficacia"


def test_guardar_crea_y_luego_reemplaza(cliente, supuestos, token):
    epi = token(("EPIDEMIOLOGO",))
    r = cliente.put("/api/v1/intervention-types/CUBREBOCAS/effectiveness?format=json", headers=epi, json=SUPUESTO)
    assert r.status_code == 201 and r.get_json()["code"] == "CUBREBOCAS"
    r = cliente.put("/api/v1/intervention-types/CUBREBOCAS/effectiveness?format=json", headers=epi,
                    json=dict(SUPUESTO, valor=0.5, min=None, max=None))
    assert r.status_code == 200 and r.get_json()["valor"] == 0.5
    assert [b[1] for b in supuestos.bitacora] == ["CREATE", "UPDATE"]


def test_por_enfermedad(cliente, supuestos, token):
    r = cliente.put("/api/v1/intervention-types/CUBREBOCAS/effectiveness?format=json",
                    headers=token(("ADMINISTRADOR",)), json=dict(SUPUESTO, enfermedad="sars_cov_2_ancestral"))
    assert r.status_code == 201 and r.get_json()["enfermedad"] == "SARS_COV_2_ANCESTRAL"
    r = cliente.put("/api/v1/intervention-types/CUBREBOCAS/effectiveness?format=json",
                    headers=token(("ADMINISTRADOR",)), json=dict(SUPUESTO, enfermedad="NADA"))
    assert r.status_code == 422


@pytest.mark.parametrize("cambios,mensaje", [
    ({"parametro": "reduccion"}, "parámetro de efecto"),
    ({"valor": 1.5}, "de 0 a 1"),
    ({"min": 0.9}, "min <= valor <= max"),
    ({"fuente": " "}, "fuente"),
    ({"supuesto": "quizas"}, "booleano"),
    ({"color": "rojo"}, "Se requieren"),
])
def test_un_supuesto_invalido_es_422(cliente, supuestos, token, cambios, mensaje):
    r = cliente.put("/api/v1/intervention-types/CUBREBOCAS/effectiveness?format=json",
                    headers=token(("EPIDEMIOLOGO",)), json=dict(SUPUESTO, **cambios))
    assert r.status_code == 422 and mensaje in r.get_json()["detail"]
    assert supuestos.filas == {}


def test_un_tipo_sin_parametro_de_efecto_lo_dice(cliente, token):
    r = cliente.put("/api/v1/intervention-types/CIERRE_ESCUELAS/effectiveness?format=json",
                    headers=token(("EPIDEMIOLOGO",)), json=SUPUESTO)
    assert r.status_code == 422 and "reduccion" in r.get_json()["detail"]


def test_solo_epidemiologo_y_admin_cambian_supuestos(cliente, token):
    url = "/api/v1/intervention-types/CUBREBOCAS/effectiveness?format=json"
    assert cliente.put(url, json=SUPUESTO).status_code == 401
    assert cliente.put(url, json=SUPUESTO, headers=token(("ANALISTA",))).status_code == 403
    assert cliente.put("/api/v1/intervention-types/NADA/effectiveness?format=json", json=SUPUESTO,
                       headers=token(("EPIDEMIOLOGO",))).status_code == 404


def test_supuesto_en_xml(cliente, supuestos, token):
    xml = (b"<supuesto><parametro>eficacia</parametro><valor>0.85</valor><fuente>Chu 2020</fuente>"
           b"<supuesto>true</supuesto></supuesto>")
    r = cliente.put("/api/v1/intervention-types/CUBREBOCAS/effectiveness?format=json",
                    headers={**token(("EPIDEMIOLOGO",)), "Content-Type": "application/xml"}, data=xml)
    assert r.status_code == 201 and r.get_json()["supuesto"] is True
