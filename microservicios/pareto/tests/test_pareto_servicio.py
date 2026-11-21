from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import xmlschema

from microservicios.pareto import datos as consultas_sql, dominio
from microservicios.pareto import rutas
from procesamiento.analitica import METRICAS_IMPACTO, comparar
from procesamiento.motor import AVISO_SIMULACION, simular
from procesamiento.tests.test_motor import escenario

RAIZ = Path(__file__).resolve().parents[3]


def fila(id_, costo, impacto, dominado_por=()):
    return {"id": id_, "nombre": "SIM-%05d - Escenario" % id_, "costo": costo, "costo_pesos": None,
            "impacto": impacto, "desglose_costo": [], "dominado": bool(dominado_por),
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

    monkeypatch.setattr(dominio, "construir_comparacion_costo_impacto",
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
# costo_adicional y costo_por_unidad_evitada. Sin el precio de la vacuna, costo_pesos va nulo
# en la fila y en el desglose, con un aviso (D3). El XSD acepta todas las formas.
@pytest.mark.parametrize("con_pesos", [True, False])
@pytest.mark.parametrize("base", [None, 12])
def test_la_salida_real_del_motor_valida_contra_el_xsd(cliente, token, monkeypatch, base, con_pesos):
    cierre = {"tipo": "CIERRE_ESCUELAS", "dia_inicio": 7, "dia_fin": 60, "params": {"reduccion": 1.0}}
    vacuna = {"tipo": "VACUNACION", "dia_inicio": 10, "cobertura": 0.7,
              "params": {"eficacia": 0.9, "dosis_diarias": 2000, "prioridad": "edad_desc",
                         "edad_minima": 60}}
    entradas = []
    for id_, intervenciones in ((12, []), (15, [cierre, vacuna])):
        esc = escenario(intervenciones=intervenciones)
        entradas.append({"id": id_, "nombre": "SIM-%05d - Escenario" % id_, "escenario": esc,
                         "resultado": simular(esc, 982314)})
    costos = {"CIERRE_ESCUELAS": {"valor": 10.0, "fuente": "prueba", "supuesto": False}}
    if con_pesos:
        costos["VACUNACION"] = {"valor": 300.0, "supuesto": True}
    factores = {"VACUNACION": {"valor": 0.5, "supuesto": True}}
    real = comparar(entradas, costos, base=base, factores=factores)
    assert (real["filas"][1]["costo_pesos"] is None) is not con_pesos
    monkeypatch.setattr(dominio, "construir_comparacion_costo_impacto",
                        lambda run_ids, metrica="fallecimientos": (real, []))
    r = cliente.get("/api/v1/pareto?runs=12,15", headers=token())
    assert r.status_code == 200
    xml = r.data.decode("utf-8")
    xmlschema.XMLSchema(str(RAIZ / "docs/contratos/pareto/pareto.xsd")).validate(xml)
    assert ("Falta el costo unitario en pesos de VACUNACION" in xml) is not con_pesos


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


@pytest.fixture
def versiones(monkeypatch):
    def construir(version_id):
        if version_id == 404:
            return None, None, ["La version de escenario no existe."]
        if version_id == 5:
            return None, {"id": 5}, ["La version de escenario no esta aprobada."]
        return escenario(), {"id": version_id}, []

    monkeypatch.setattr(dominio, "construir_escenario_desde_version", construir)


def test_sensibilidad_por_porcentaje(cliente, token, versiones):
    r = cliente.get("/api/v1/pareto/sensitivity?version=7&parameter=r0&percent=-20,20&format=json",
                    headers=token())
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["aviso"] == AVISO_SIMULACION and datos["categoria"] == "exploratoria"
    assert [f["valor"] for f in datos["filas"]] == [1.44, 1.8, 2.16]
    assert [f["es_base"] for f in datos["filas"]] == [False, True, False]
    medias = [f["media"] for f in datos["filas"]]
    assert medias == sorted(medias)


def test_sensibilidad_por_valores_xml_valida_contra_el_xsd(cliente, token, versiones):
    r = cliente.get("/api/v1/pareto/sensitivity?version=7&parameter=infeccioso_dias&values=4,6"
                    "&metric=hospitalizaciones", headers=token())
    assert r.status_code == 200
    xmlschema.XMLSchema(str(RAIZ / "docs/contratos/pareto/pareto.xsd")).validate(r.data.decode("utf-8"))


@pytest.mark.parametrize("consulta,estado", [
    ("version=7&parameter=r0", 422),
    ("version=7&parameter=r0&values=1.5&percent=10", 422),
    ("version=7&parameter=letalidad&values=1.5", 422),
    ("version=7&parameter=r0&values=abc", 422),
    ("version=7&parameter=r0&values=0", 422),
    ("version=7&parameter=r0&percent=-100", 422),
    ("version=7&parameter=r0&values=1,2,3,4,5,6,7,8,9,10", 422),
    ("version=7&parameter=r0&values=1.5&metric=costo", 422),
    ("parameter=r0&values=1.5", 422),
    ("version=5&parameter=r0&values=1.5", 422),
    ("version=404&parameter=r0&values=1.5", 404),
])
def test_sensibilidad_invalida(cliente, token, versiones, consulta, estado):
    r = cliente.get("/api/v1/pareto/sensitivity?format=json&" + consulta, headers=token())
    assert r.status_code == estado


def test_sensibilidad_pide_token_y_rol(cliente, token, versiones):
    ruta = "/api/v1/pareto/sensitivity?version=7&parameter=r0&values=1.5"
    assert cliente.get(ruta).status_code == 401
    assert cliente.get(ruta, headers=token(("CAPTURISTA",))).status_code == 403


def test_calibracion_dice_que_no_hay(cliente, token):
    r = cliente.get("/api/v1/pareto/calibration?format=json", headers=token())
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["disponible"] is False and datos["ejecucion"] == "no_disponible"
    assert {m["estado"] for m in datos["modelos"]} == {"sin_calibrar"}
    assert {m["categoria"] for m in datos["modelos"]} == {"exploratoria"}
    xml = cliente.get("/api/v1/pareto/calibration?disease=1&region=2", headers=token())
    xmlschema.XMLSchema(str(RAIZ / "docs/contratos/pareto/pareto.xsd")).validate(xml.data.decode("utf-8"))


@pytest.mark.parametrize("consulta", ["engine=otro", "disease=0", "region=x"])
def test_calibracion_invalida(cliente, token, consulta):
    assert cliente.get("/api/v1/pareto/calibration?format=json&" + consulta, headers=token()).status_code == 422


def test_calibracion_no_se_ejecuta(cliente, token):
    assert cliente.post("/api/v1/pareto/calibration", headers=token()).status_code == 405
    assert cliente.get("/api/v1/pareto/calibration", headers={}).status_code == 401
    assert cliente.get("/api/v1/pareto/calibration", headers=token(("CAPTURISTA",))).status_code == 403


@pytest.mark.parametrize("rol", ["INVESTIGADOR", "AUTORIDAD_SANITARIA"])
def test_los_perfiles_de_lectura_ven_la_frontera(cliente, token, rol):
    assert cliente.get("/api/v1/pareto?runs=12,15&format=json", headers=token((rol,))).status_code == 200


def test_las_corridas_de_otra_region_son_403(cliente, token, llamadas, alcance_falso, monkeypatch):
    monkeypatch.setattr(consultas_sql, "regiones_de_corridas", lambda ids: {9, 10})
    alcance_falso["regiones"] = [9]
    r = cliente.get("/api/v1/pareto?runs=12,15&format=json", headers=token())
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"
    assert llamadas == []
    alcance_falso["regiones"] = [9, 10]
    assert cliente.get("/api/v1/pareto?runs=12,15&format=json", headers=token()).status_code == 200


def test_la_sensibilidad_de_una_version_de_otra_region_es_403(
        cliente, token, versiones, alcance_falso, monkeypatch):
    monkeypatch.setattr(consultas_sql, "region_de_version", lambda version_id: 10)
    alcance_falso["regiones"] = [9]
    r = cliente.get("/api/v1/pareto/sensitivity?version=7&parameter=r0&percent=20&format=json",
                    headers=token())
    assert r.status_code == 403
    alcance_falso["regiones"] = [10]
    assert cliente.get("/api/v1/pareto/sensitivity?version=7&parameter=r0&percent=20&format=json",
                       headers=token()).status_code == 200
