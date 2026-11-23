"""Contrato, rutas y Dockerfile de tipos-intervencion, indicadores, series, zonas, comparacion,
pareto, corridas, resultados, notificaciones, estado-servicios, dispositivos, evidencias y vacunas
(simulador tiene los suyos). Una operación con "x-binario" regresa un archivo tal cual: no lleva
JSON ni XML ni ejemplos."""
import ast
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]

# (servicio del catálogo, paquete de Python, puerto, rutas públicas)
SERVICIOS = [
    # Identidad: sus ejemplos por ruta, pendientes del segundo parcial (E6).
    # Pública salvo el restablecimiento del MFA de una cuenta, que es de ADMINISTRADOR (D40).
    ("auth", "auth", 5201, None),
    ("sesiones", "sesiones", 5202, None),
    ("usuarios", "usuarios", 5203, False),
    ("roles", "roles", 5204, False),
    # Pública salvo guardar un supuesto de efectividad, que es de EPIDEMIOLOGO y ADMINISTRADOR (D58).
    ("tipos-intervencion", "tipos_intervencion", 5215, None),
    # Pública salvo la exportación, que pide sesión para auditar quién exporta (D36).
    ("indicadores", "indicadores", 5251, None),
    ("series", "series", 5252, False),
    ("zonas", "zonas", 5253, False),
    ("comparacion", "comparacion", 5244, False),
    ("pareto", "pareto", 5245, False),
    ("calibracion", "calibracion", 5246, False),
    ("corridas", "corridas", 5241, False),
    ("resultados", "resultados", 5243, False),
    ("notificaciones", "notificaciones", 5261, False),
    ("estado-servicios", "estado_servicios", 5262, True),
    ("dispositivos", "dispositivos", 5223, False),
    ("evidencias", "evidencias", 5224, False),
    ("vacunas", "vacunas", 5225, False),
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
            if not item.get("x-binario"):
                assert {"application/json", "application/xml"} <= set(contenido)
            en_contrato.add((ruta, metodo, item.get("security") == [{"bearerAuth": []}]))
    assert en_contrato == rutas_declaradas(paquete)
    if publico is not None:
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
            if item.get("x-binario"):
                continue
            ejemplo = carpeta / "ejemplos" / item["operationId"]
            contenido = exito(item)["content"]
            en_json = json.loads(ejemplo.with_suffix(".json").read_text(encoding="utf-8"))
            en_xml = ejemplo.with_suffix(".xml").read_text(encoding="utf-8")
            assert contenido["application/json"]["example"] == en_json
            assert contenido["application/xml"]["examples"]["respuesta"]["value"] == en_xml
            ET.fromstring(en_xml.encode("utf-8"))


def test_toda_ruta_con_limite_documenta_el_429():
    publicas = {("auth", "/api/v1/auth/captcha"), ("auth", "/api/v1/auth/login"),
                ("regiones", "/api/v1/regions"), ("regiones", "/api/v1/regions/{region_id}")}
    for archivo in (RAIZ / "docs/contratos").glob("*/openapi.json"):
        contrato = json.loads(archivo.read_text(encoding="utf-8"))
        for ruta, metodos in contrato["paths"].items():
            for item in metodos.values():
                if item.get("security") == [{"bearerAuth": []}] or (archivo.parent.name, ruta) in publicas:
                    respuesta = item["responses"]["429"]
                    assert "Retry-After" in respuesta["headers"], (archivo.parent.name, ruta)
