"""XSD de los contratos (D15): las respuestas de los servicios y los ejemplos validan con xmlschema."""
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import xmlschema

from backend_web import queries

CONTRATOS = Path(__file__).resolve().parents[3] / "docs/contratos"
PROBLEM = xmlschema.XMLSchema(str(CONTRATOS / "comun/problem.xsd"))
ENFERMEDAD = xmlschema.XMLSchema(str(CONTRATOS / "enfermedades/enfermedad.xsd"))
PARAMETROS = xmlschema.XMLSchema(str(CONTRATOS / "parametros/parametros.xsd"))
RESULTADO = xmlschema.XMLSchema(str(CONTRATOS / "resultados/resultado.xsd"))

FICHA = {"id": 1, "code": "SARS_COV_2_ANCESTRAL", "name": "COVID-19", "description": None,
         "is_active": True, "created_at": datetime(2026, 9, 1, 16, tzinfo=timezone.utc)}

# Los formatos que conviven en diseases.default_params.
PARAMS = {
    "r0": {"valor": 2.5, "fuente": "Liu et al. 2020", "supuesto": False},
    "infeccioso_dias": {"valor": 4.8, "fuente": None, "supuesto": True},
    "incubacion_dias": {"desv": 1.5, "dist": "lognormal", "media": 5.1},
    "letalidad_por_edad": {"valor": {"0-19": 3.11e-05, "80+": 0.00526},
                           "fuente": "Verity et al. 2020", "supuesto": True},
    "prob_asintomatico": 0.35,
}


@pytest.fixture
def enfermedades(crear_cliente, monkeypatch):
    monkeypatch.setattr(queries, "get_enfermedad", lambda i: dict(FICHA) if i == 1 else None)
    return crear_cliente("enfermedades")


@pytest.fixture
def parametros(crear_cliente, monkeypatch):
    def fila(i):
        return {**FICHA, "default_params": PARAMS} if i == 1 else None
    monkeypatch.setattr(queries, "get_enfermedad", fila)
    return crear_cliente("parametros")


ESQUEMAS = {"enfermedad": ENFERMEDAD, "parametros": PARAMETROS, "resultado": RESULTADO}
EJEMPLOS = [a for a in sorted(CONTRATOS.glob("*/ejemplos/*.xml"))
            if ET.parse(a).getroot().tag in ESQUEMAS]


@pytest.mark.parametrize("archivo", EJEMPLOS, ids=lambda a: a.name)
def test_ejemplos_de_los_contratos(archivo):
    ESQUEMAS[ET.parse(archivo).getroot().tag].validate(str(archivo))


def test_enfermedad_real(enfermedades):
    r = enfermedades.get("/api/v1/diseases/1")
    assert r.status_code == 200
    ENFERMEDAD.validate(r.data.decode("utf-8"))


def test_parametros_reales_en_todos_sus_formatos(parametros):
    r = parametros.get("/api/v1/diseases/1/parameters")
    assert r.status_code == 200
    PARAMETROS.validate(r.data.decode("utf-8"))


def test_parametros_con_letalidad_por_edad_sin_fuente(parametros, monkeypatch):
    plano = {"letalidad_por_edad": {"0-19": 0.00002, "80+": 0.10}}
    monkeypatch.setattr(queries, "get_enfermedad", lambda i: {**FICHA, "default_params": plano})
    PARAMETROS.validate(parametros.get("/api/v1/diseases/1/parameters").data.decode("utf-8"))


@pytest.mark.parametrize("ruta,metodo,estado", [
    ("/api/v1/diseases/999", "get", 404),
    ("/api/v1/diseases", "post", 401),
])
def test_errores_reales(enfermedades, ruta, metodo, estado):
    r = getattr(enfermedades, metodo)(ruta)
    assert r.status_code == estado
    assert r.content_type.startswith("application/problem+xml")
    PROBLEM.validate(r.data.decode("utf-8"))


@pytest.mark.parametrize("esquema,documento", [
    (PROBLEM, "<problem><type>about:blank</type><title>Not Found</title>"
              "<status tipo='numero'>404</status><detail>x</detail><instance>/</instance></problem>"),
    (ENFERMEDAD, "<enfermedad><id>1</id></enfermedad>"),
    (PARAMETROS, "<parametros><disease_id tipo='numero'>1</disease_id><parametros>"
                 "<r0><valor tipo='numero'>alto</valor></r0></parametros></parametros>"),
])
def test_documento_invalido_se_rechaza(esquema, documento):
    assert not esquema.is_valid(documento)
