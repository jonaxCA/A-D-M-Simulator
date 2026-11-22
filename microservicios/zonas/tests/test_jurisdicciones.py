"""Casos por jurisdicción sanitaria (F7) y el archivo que la define."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from backend_web import queries
from microservicios.zonas import jurisdicciones

RAIZ = Path(__file__).resolve().parents[3]
GENERADOR = RAIZ / "datos/scripts/build_jurisdicciones.py"


def _generador():
    spec = importlib.util.spec_from_file_location("build_jurisdicciones", GENERADOR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_el_archivo_sale_de_su_generador():
    """datos/geo no se edita a mano (datos/AGENTS.md): se cambia el script y se regenera."""
    generador = _generador()
    catalogo = json.loads(Path(generador.CATALOGO).read_text(encoding="utf-8"))
    assert generador.texto(generador.construir(catalogo)) == \
        jurisdicciones.ARCHIVO.read_text(encoding="utf-8")


def test_los_51_municipios_una_sola_vez():
    datos = jurisdicciones.catalogo()
    claves = [c for j in datos["jurisdicciones"] for c in j["municipios"]] + list(datos["compartidos"])
    catalogo = json.loads((RAIZ / "datos/geo/nl_catalogo_oficial.json").read_text(encoding="utf-8"))
    assert sorted(claves) == sorted("19" + c for c in catalogo)
    assert [j["numero"] for j in datos["jurisdicciones"]] == list(range(1, 9))
    assert datos["compartidos"] == {"19039": [1, 2, 3]}


def test_un_nombre_que_no_esta_en_el_catalogo_detiene_al_generador():
    generador = _generador()
    catalogo = json.loads(Path(generador.CATALOGO).read_text(encoding="utf-8"))
    del catalogo["051"]
    with pytest.raises(ValueError):
        generador.construir(catalogo)


def fila(code, name, population, casos=0, graves=0, ult7=0, prev7=0):
    return {"code": code, "name": name, "population": population, "casos": casos,
            "graves": graves, "ult7": ult7, "prev7": prev7}


@pytest.fixture
def base(monkeypatch):
    estado = SimpleNamespace(pedidas=[], filas=[
        fila("19039", "Monterrey", 1142994, casos=40, graves=3, ult7=20, prev7=10),
        fila("19006", "Apodaca", 656464, casos=10, ult7=6, prev7=6),
        fila("19026", "Guadalupe", 643143, casos=5, graves=1, ult7=2, prev7=1),
        fila("19031", "Juárez", 471523),
        fila("19038", "Montemorelos", 67428, casos=2, ult7=2),
    ])

    def query(sql, params=None, one=False):
        estado.pedidas.append((sql, params))
        return [dict(f) for f in estado.filas]

    monkeypatch.setattr(jurisdicciones, "query", query)
    return estado


def test_monterrey_aparte_y_cada_jurisdiccion_con_sus_municipios(base):
    grupos = {g["clave"]: g for g in jurisdicciones.calcular(30)}
    assert list(grupos)[:2] == ["compartido-19039", "2"]
    monterrey = grupos["compartido-19039"]
    assert monterrey["nombre"] == "Monterrey (jurisdicciones 1, 2 y 3)"
    assert (monterrey["numeros"], monterrey["casos"], monterrey["graves"]) == ([1, 2, 3], 40, 3)
    assert (monterrey["variacion"], monterrey["estado"]) == (100.0, "critico")
    cuatro = grupos["4"]
    assert cuatro["nombre"] == "Jurisdicción Sanitaria No. 4"
    assert [m["nombre"] for m in cuatro["municipios"]] == ["Apodaca", "Guadalupe", "Juárez"]
    assert (cuatro["poblacion"], cuatro["casos"], cuatro["graves"]) == (1771130, 15, 1)
    assert cuatro["incidencia"] == round(15 / 1771130 * 100000, 1)
    assert (cuatro["variacion"], cuatro["estado"]) == (14.3, "estable")
    assert grupos["7"]["casos"] == 2 and grupos["7"]["variacion"] == 100.0
    assert "1" not in grupos  # la 1 es solo una parte de Monterrey


def test_un_municipio_sin_jurisdiccion_no_pierde_sus_casos(base):
    base.filas.append(fila("19999", "Nuevo", 1000, casos=4))
    assert jurisdicciones.calcular(30)[-1]["clave"] == "sin-jurisdiccion"


def test_la_consulta_es_la_de_la_tabla_por_zona(base):
    jurisdicciones.calcular(7, disease_id=3)
    ((sql, params),) = base.pedidas
    assert "c.status IN ('pendiente', 'validado')" in sql and "c.disease_id = %(disease_id)s" in sql
    assert (params["dias"], params["ventana"], params["estado"]) == (6, 13, "19")


# --------------------------------------------------------------------------- la ruta

@pytest.fixture
def cliente(crear_cliente, base, monkeypatch):
    monkeypatch.setattr(queries, "get_enfermedad", lambda i: {"id": i} if i == 1 else None)
    return crear_cliente("zonas")


def test_pide_sesion(cliente):
    assert cliente.get("/api/v1/zones/jurisdictions?format=json").status_code == 401


def test_por_jurisdiccion_en_json_con_su_fuente(cliente, token):
    datos = cliente.get("/api/v1/zones/jurisdictions?days=7&disease_id=1&format=json",
                        headers=token()).get_json()
    assert datos["filtros"] == {"disease_id": 1, "days": 7}
    assert "artículo 27" in datos["fuente"]["documento"]
    assert len(datos["jurisdicciones"]) == 8  # Monterrey y las jurisdicciones 2 a 8


def test_por_jurisdiccion_en_xml(cliente, token):
    raiz = ET.fromstring(cliente.get("/api/v1/zones/jurisdictions", headers=token()).data)
    assert raiz.tag == "zonas_por_jurisdiccion"
    primera = raiz.find("jurisdicciones/jurisdiccion")
    assert [n.text for n in primera.find("numeros").findall("numero")] == ["1", "2", "3"]
    assert primera.find("municipios/municipio").findtext("region_code") == "19039"


@pytest.mark.parametrize("consulta,estado", [("days=14", 422), ("disease_id=99", 404)])
def test_filtros_invalidos(cliente, token, consulta, estado):
    assert cliente.get("/api/v1/zones/jurisdictions?%s&format=json" % consulta,
                       headers=token()).status_code == estado


def test_la_imagen_trae_el_archivo():
    docker = (RAIZ / "microservicios/zonas/Dockerfile").read_text(encoding="utf-8")
    assert "COPY datos/geo/nl_jurisdicciones_sanitarias.json" in docker
    assert "!datos/geo/nl_jurisdicciones_sanitarias.json" in (RAIZ / ".dockerignore").read_text(encoding="utf-8")
