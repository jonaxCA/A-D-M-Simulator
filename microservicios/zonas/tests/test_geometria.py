"""Geometría oficial de los municipios y ubicar un punto (F7)."""
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from microservicios.zonas import geometria, jurisdicciones

RAIZ = Path(__file__).resolve().parents[3]
WEB = RAIZ / "frontend_web/app/static/js/nl_municipios.json"


def test_es_la_misma_geometria_que_dibuja_la_web():
    """Las dos salen de datos/scripts/build_municipios_inegi.py: si una cambia sin la otra, el
    mapa de la web y el de las apps dejarían de coincidir."""
    datos = json.loads(geometria.ARCHIVO.read_text(encoding="utf-8"))
    web = json.loads(WEB.read_text(encoding="utf-8"))
    assert datos["features"] == web["features"]
    assert "INEGI" in datos["fuente"]["documento"] and datos["fuente"]["tolerancia_grados"] == 0.0012


def test_los_51_municipios_del_catalogo_inegi():
    catalogo = json.loads((RAIZ / "datos/geo/nl_catalogo_oficial.json").read_text(encoding="utf-8"))
    datos = json.loads(geometria.ARCHIVO.read_text(encoding="utf-8"))
    assert {f["properties"]["region_code"]: f["properties"]["name"] for f in datos["features"]} == \
        {"19" + c: n for c, n in catalogo.items()}


@pytest.mark.parametrize("lat,lon,codigo", [
    (25.6866, -100.3161, "19039"),   # Monterrey, centro
    (25.7781, -100.1883, "19006"),   # Apodaca
    (24.851802, -99.529129, "19033"),   # Linares, su centroide
    (23.860137, -100.306246, "19014"),  # Doctor Arroyo, su centroide
])
def test_ubica_un_punto_en_su_municipio(lat, lon, codigo):
    propiedades, aproximado = geometria.localiza(lat, lon)
    assert propiedades["region_code"] == codigo and aproximado is False


def test_un_punto_fuera_de_nuevo_leon():
    assert geometria.localiza(19.4326, -99.1332) == (None, False)  # Ciudad de México


def test_en_la_rendija_entre_dos_fronteras_toma_el_mas_cercano(monkeypatch):
    cuadro = lambda x0, x1: [[[x0, 0.0], [x1, 0.0], [x1, 1.0], [x0, 1.0], [x0, 0.0]]]
    monkeypatch.setattr(geometria, "_indice", lambda: [
        ((0.0, 0.0, 1.0, 1.0), [cuadro(0.0, 1.0)], {"region_code": "A", "name": "A"}),
        ((1.002, 0.0, 2.0, 1.0), [cuadro(1.002, 2.0)], {"region_code": "B", "name": "B"})])
    assert geometria.localiza(0.5, 1.0005) == ({"region_code": "A", "name": "A"}, True)
    assert geometria.localiza(0.5, 1.0016) == ({"region_code": "B", "name": "B"}, True)
    assert geometria.localiza(0.5, 3.0) == (None, False)


def test_un_hueco_no_es_parte_del_municipio(monkeypatch):
    exterior = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]
    hueco = [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]
    monkeypatch.setattr(geometria, "_indice", lambda: [
        ((0, 0, 4, 4), [[exterior, hueco]], {"region_code": "A", "name": "A"})])
    assert geometria.localiza(0.5, 0.5)[0] is not None
    assert geometria.localiza(2, 2) == (None, False)


def test_la_jurisdiccion_de_un_municipio():
    assert jurisdicciones.de_municipio("19006", "Apodaca") == {
        "clave": "4", "nombre": "Jurisdicción Sanitaria No. 4", "numeros": [4]}
    assert jurisdicciones.de_municipio("19039", "Monterrey") == {
        "clave": "compartido-19039", "nombre": "Monterrey (jurisdicciones 1, 2 y 3)", "numeros": [1, 2, 3]}
    assert jurisdicciones.de_municipio("19999", "Nuevo") is None


# --------------------------------------------------------------------------- las rutas

@pytest.fixture
def cliente(crear_cliente, monkeypatch):
    monkeypatch.setattr(geometria, "query", lambda sql, params=None, one=False: [
        {"id": 3, "code": "19039"}, {"id": 12, "code": "19006"}])
    return crear_cliente("zonas")


@pytest.mark.parametrize("ruta", ["/api/v1/zones/geometry", "/api/v1/zones/locate?lat=25.7&lon=-100.3"])
def test_piden_sesion(cliente, ruta):
    assert cliente.get(ruta).status_code == 401


def test_la_geometria_tal_cual_con_etag(cliente, token):
    cabeceras = token()
    r = cliente.get("/api/v1/zones/geometry", headers=cabeceras)
    assert r.status_code == 200 and r.content_type.startswith("application/geo+json")
    assert r.data == geometria.ARCHIVO.read_bytes()
    assert r.headers["ETag"] == geometria.etag() and "max-age" in r.headers["Cache-Control"]
    r = cliente.get("/api/v1/zones/geometry", headers=dict(cabeceras, **{"If-None-Match": geometria.etag()}))
    assert r.status_code == 304 and r.data == b""


def test_ubicar_en_json(cliente, token):
    datos = cliente.get("/api/v1/zones/locate?lat=25.6866&lon=-100.3161&format=json", headers=token()).get_json()
    assert datos["en_nuevo_leon"] is True and datos["aproximado"] is False
    assert datos["municipio"] == {"region_id": 3, "region_code": "19039", "nombre": "Monterrey"}
    assert datos["jurisdiccion"]["clave"] == "compartido-19039"
    assert datos["precision_m"] == 130


def test_ubicar_fuera_y_en_xml(cliente, token):
    raiz = ET.fromstring(cliente.get("/api/v1/zones/locate?lat=19.43&lon=-99.13", headers=token()).data)
    assert raiz.tag == "ubicacion" and raiz.findtext("en_nuevo_leon") == "false"
    assert raiz.find("municipio").get("nil") == "true"


@pytest.mark.parametrize("consulta", ["lat=25.7", "lon=-100.3", "lat=x&lon=-100", "lat=95&lon=-100",
                                      "lat=25&lon=-181", "lat=nan&lon=-100", "lat=inf&lon=-100"])
def test_coordenadas_invalidas_son_422(cliente, token, consulta):
    assert cliente.get("/api/v1/zones/locate?%s&format=json" % consulta, headers=token()).status_code == 422


def test_la_imagen_trae_la_geometria():
    docker = (RAIZ / "microservicios/zonas/Dockerfile").read_text(encoding="utf-8")
    assert "datos/geo/nl_municipios.geojson" in docker
    assert "!datos/geo/nl_municipios.geojson" in (RAIZ / ".dockerignore").read_text(encoding="utf-8")
