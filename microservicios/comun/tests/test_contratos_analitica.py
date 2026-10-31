"""Contrato, rutas y Dockerfile de tipos-intervencion, indicadores, series, zonas, comparacion,
pareto, corridas, resultados, notificaciones, estado-servicios y dispositivos (simulador tiene
los suyos)."""
import ast
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]

# (servicio del catálogo, paquete de Python, puerto, rutas públicas)
SERVICIOS = [
    ("tipos-intervencion", "tipos_intervencion", 5215, True),
    ("indicadores", "indicadores", 5251, True),
    ("series", "series", 5252, False),
    ("zonas", "zonas", 5253, False),
    ("comparacion", "comparacion", 5244, False),
    ("pareto", "pareto", 5245, False),
    ("corridas", "corridas", 5241, False),
    ("resultados", "resultados", 5243, False),
    ("notificaciones", "notificaciones", 5261, False),
    ("estado-servicios", "estado_servicios", 5262, True),
    ("dispositivos", "dispositivos", 5223, False),
]


def exito(item):
    """La respuesta 2xx de una operación: 200, o 201 y 202 en las que crean."""
    return next(v for k, v in item["responses"].items() if k.startswith("2"))


def rutas_declaradas(paquete):
    """(ruta, método, protegida) de cada función decorada en rutas.py."""
    programa = ast.parse((RAIZ / "microservicios" / paquete / "rutas.py").read_text(encoding="utf-8"))
    rutas = set()
    for nodo in ast.walk(programa):
        if not isinstance(nodo, ast.FunctionDef):
            continue
        ruta, protegida = None, False
        for decorador in nodo.decorator_list:
            if (isinstance(decorador, ast.Call) and isinstance(decorador.func, ast.Attribute)
                    and decorador.func.attr in ("get", "post", "put", "delete", "patch")):
                ruta = (re.sub(r"<(?:int:)?([^>]+)>", r"{\1}", decorador.args[0].value),
                        decorador.func.attr)
            elif isinstance(decorador, ast.Call) and getattr(decorador.func, "id", "") == "requiere_token":
                protegida = True
        if ruta:
            rutas.add(ruta + (protegida,))
    return rutas


@pytest.mark.parametrize("servicio,paquete,puerto,publico", SERVICIOS)
def test_contrato_igual_a_las_rutas(servicio, paquete, puerto, publico):
    contrato = json.loads((RAIZ / "docs/contratos" / servicio / "openapi.json").read_text(encoding="utf-8"))
    assert contrato["openapi"] == "3.0.3"
    assert contrato["servers"][0]["url"].endswith(":%d" % puerto)
    en_contrato = set()
    for ruta, metodos in contrato["paths"].items():
        for metodo, item in metodos.items():
            contenido = exito(item)["content"]
            assert {"application/json", "application/xml"} <= set(contenido)
            en_contrato.add((ruta, metodo, item.get("security") == [{"bearerAuth": []}]))
    assert en_contrato == rutas_declaradas(paquete)
    assert all(not protegida for *_, protegida in en_contrato) is publico


@pytest.mark.parametrize("servicio,paquete,puerto,publico", SERVICIOS)
def test_dockerfile_y_app(servicio, paquete, puerto, publico):
    docker = (RAIZ / "microservicios" / paquete / "Dockerfile").read_text(encoding="utf-8")
    # estado-servicios arranca con python -m, como simulador: su sondeo corre junto al servidor.
    assert ("microservicios.%s.app:app" % paquete in docker
            or '"-m", "microservicios.%s"' % paquete in docker)
    assert "COPY docs/contratos/%s/" % servicio in docker
    assert "HEALTHCHECK" in docker and "USER epidemia" in docker
    app = (RAIZ / "microservicios" / paquete / "app.py").read_text(encoding="utf-8")
    assert 'crear_app("%s"' % servicio in app
    assert "port=%d" % puerto in app


@pytest.mark.parametrize("servicio,paquete,puerto,publico", SERVICIOS)
def test_ejemplos_json_y_xml_por_ruta(servicio, paquete, puerto, publico):
    """Un ejemplo JSON y uno XML por ruta, iguales a los que muestra Swagger."""
    from xml.etree import ElementTree as ET
    carpeta = RAIZ / "docs/contratos" / servicio
    contrato = json.loads((carpeta / "openapi.json").read_text(encoding="utf-8"))
    for metodos in contrato["paths"].values():
        for item in metodos.values():
            ejemplo = carpeta / "ejemplos" / item["operationId"]
            contenido = exito(item)["content"]
            en_json = json.loads(ejemplo.with_suffix(".json").read_text(encoding="utf-8"))
            en_xml = ejemplo.with_suffix(".xml").read_text(encoding="utf-8")
            assert contenido["application/json"]["example"] == en_json
            assert contenido["application/xml"]["examples"]["respuesta"]["value"] == en_xml
            ET.fromstring(en_xml.encode("utf-8"))
