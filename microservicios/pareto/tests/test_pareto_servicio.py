from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import xmlschema

from backend_web import simulaciones
from microservicios.pareto import rutas
from procesamiento.motor import AVISO_SIMULACION, METRICAS_IMPACTO, comparar, simular
from procesamiento.tests.test_motor import escenario

RAIZ = Path(__file__).resolve().parents[3]


def fila(id_, costo, impacto, dominado_por=()):
    return {"id": id_, "nombre": "SIM-%05d - Escenario" % id_, "costo": costo, "impacto": impacto,
            "desglose_costo": [], "dominado": bool(dominado_por),
            "dominado_por": list(dominado_por)}


# Lo que regresa el monolito para cualquier par de corridas completadas. No pide base.
COMPARACION = {"base": None, "filas": [fila(12, 0, 100), fila(15, 5000.0, 120, [12])],
               "frontera": [12], "trazabilidad_costos": [], "modelo_costo": "unitario x dosis",
               "avisos": []}


@pytest.fixture
def llamadas(monkeypatch):
    registro = []

    def comparacion_costo_impacto(run_ids, metrica="fallecimientos"):
        registro.append((list(run_ids), metrica))
        if 99 in run_ids:
            return None, ["La corrida SIM-00099 no esta completada.",
                          "SIM-00015 no tiene resultados guardados."]
        if metrica not in METRICAS_IMPACTO:
            return None, ["Metrica '%s' no valida." % metrica]
        return dict(COMPARACION, metrica=metrica), []

    monkeypatch.setattr(simulaciones, "construir_comparacion_costo_impacto",
                        comparacion_costo_impacto)
    return registro


@pytest.fixture
def cliente(crear_cliente, llamadas):
    return crear_cliente("pareto")


def test_sin_token_es_401(cliente):
    assert cliente.get("/api/v1/pareto?runs=12,15").status_code == 401


def test_capturista_no_entra(cliente, token):
    r = cliente.get("/api/v1/pareto?runs=12,15&format=json", headers=token(("CAPTURISTA",)))
    assert r.status_code == 403


@pytest.mark.parametrize("rol", rutas.ROLES)
def test_compara_con_la_metrica_por_omision(cliente, token, llamadas, rol):
    r = cliente.get("/api/v1/pareto?runs=15,12,15&format=json", headers=token((rol,)))
    assert r.status_code == 200
    assert llamadas == [([15, 12], "fallecimientos")]
    datos = r.get_json()
    assert datos["aviso"] == AVISO_SIMULACION
    assert datos["frontera"] == [12] and datos["base"] is None
    assert [f["dominado_por"] for f in datos["filas"]] == [[], [12]]


def test_otra_metrica(cliente, token, llamadas):
    r = cliente.get("/api/v1/pareto?runs=12,15&metric=hospitalizaciones&format=json",
                    headers=token())
    assert r.status_code == 200
    assert llamadas == [([12, 15], "hospitalizaciones")]
    assert r.get_json()["metrica"] == "hospitalizaciones"


def test_xml_por_omision(cliente, token):
    r = cliente.get("/api/v1/pareto?runs=12,15", headers=token())
    assert r.mimetype == "application/xml"
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "pareto"
    assert [f.findtext("id") for f in raiz.findall("filas/fila")] == ["12", "15"]
    assert [c.text for c in raiz.findall("frontera/corrida")] == ["12"]
    assert [c.text for c in raiz.findall("filas/fila/dominado_por/corrida")] == ["12"]


# El servicio no pide escenario base (base vacío); con base salen además impacto_evitado,
# costo_adicional y costo_por_unidad_evitada. El XSD acepta las dos formas.
@pytest.mark.parametrize("base", [None, 12])
def test_la_salida_real_del_motor_valida_contra_el_xsd(cliente, token, monkeypatch, base):
    cierre = {"tipo": "CIERRE_ESCUELAS", "dia_inicio": 7, "dia_fin": 60, "params": {"reduccion": 1.0}}
    vacuna = {"tipo": "VACUNACION", "dia_inicio": 10, "cobertura": 0.7,
              "params": {"eficacia": 0.9, "dosis_diarias": 2000, "prioridad": "edad_desc",
                         "edad_minima": 60}}
    entradas = []
    for id_, intervenciones in ((12, []), (15, [cierre, vacuna])):
        esc = escenario(intervenciones=intervenciones)
        entradas.append({"id": id_, "nombre": "SIM-%05d - Escenario" % id_, "escenario": esc,
                         "resultado": simular(esc, 982314)})
    costos = {"CIERRE_ESCUELAS": {"valor": 10.0, "fuente": "prueba", "supuesto": False},
              "VACUNACION": {"valor": 300.0, "supuesto": True}}
    real = comparar(entradas, costos, base=base)
    monkeypatch.setattr(simulaciones, "construir_comparacion_costo_impacto",
                        lambda run_ids, metrica="fallecimientos": (real, []))
    r = cliente.get("/api/v1/pareto?runs=12,15", headers=token())
    assert r.status_code == 200
    xmlschema.XMLSchema(str(RAIZ / "docs/contratos/pareto/pareto.xsd")).validate(r.data.decode("utf-8"))


@pytest.mark.parametrize("runs", [None, "", "12", "12,12", "12,abc", "12,0",
                                  ",".join(str(i) for i in range(1, rutas.MAXIMO + 2))])
def test_runs_invalido_es_422_sin_calcular(cliente, token, llamadas, runs):
    ruta = "/api/v1/pareto?format=json" + ("" if runs is None else "&runs=" + runs)
    r = cliente.get(ruta, headers=token())
    assert r.status_code == 422
    assert r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert llamadas == []


def test_corridas_que_no_se_pueden_comparar_son_422_con_cada_motivo(cliente, token):
    r = cliente.get("/api/v1/pareto?runs=12,15,99&format=json", headers=token())
    assert r.status_code == 422
    detalle = r.get_json()["detail"]
    assert "SIM-00099 no esta completada" in detalle and "SIM-00015 no tiene resultados" in detalle


def test_metrica_desconocida_es_422(cliente, token):
    r = cliente.get("/api/v1/pareto?runs=12,15&metric=costo&format=json", headers=token())
    assert r.status_code == 422


def test_redis_caido_es_503(cliente, token, apagar_redis):
    encabezados = token()
    apagar_redis()
    assert cliente.get("/api/v1/pareto?runs=12,15", headers=encabezados).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/pareto/openapi.json").read_bytes()
