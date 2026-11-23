import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest
import xmlschema

from microservicios.importacion import datos

CONTRATO = Path(__file__).resolve().parents[3] / "docs/contratos/importacion"
CSV = (CONTRATO / "ejemplos/entrada_serie.csv").read_bytes()
META = {"code": "COVID19_NL_2020_SINTOMAS", "name": "Serie", "disease": "SARS_COV_2_ANCESTRAL",
        "region": "19", "metric": "casos_confirmados", "period": "semana", "source": "DGE",
        "license": "Datos abiertos", "cutoff": "2021-10-31"}
REGION_NL = 1


class Base:
    """datos.py simulado: lo que se guardaría, en memoria."""

    def __init__(self):
        self.conjuntos, self.series = {}, {}

    def ids_de(self, disease, region):
        return (3 if disease == "SARS_COV_2_ANCESTRAL" else None), (REGION_NL if region == "19" else None)

    def guardar(self, meta, ids, puntos, huella, user_id, *, contexto):
        previo = next((c for c in self.conjuntos.values() if c["code"] == meta["code"] and c["sha256"] == huella), None)
        if previo:
            return dict(previo), False
        version = 1 + sum(c["code"] == meta["code"] for c in self.conjuntos.values())
        nuevo = {"id": len(self.conjuntos) + 1, "code": meta["code"], "version": version, "name": meta["name"],
                 "disease": meta["disease"], "region": meta["region"], "region_id": ids[1],
                 "metric": meta["metric"], "period": meta["period"], "source": meta["source"],
                 "license": meta["license"], "source_url": meta["url"], "cutoff_date": meta["cutoff"],
                 "sha256": huella, "imported_by": user_id,
                 "created_at": datetime(2026, 11, 23, 16, 20, tzinfo=timezone.utc),
                 "resumen": {"puntos": len(puntos), "inicio": puntos[0][0], "fin": puntos[-1][0],
                             "total": sum(v for _, v in puntos), "maximo": max(v for _, v in puntos),
                             "periodos_en_cero": 0}}
        self.conjuntos[nuevo["id"]] = nuevo
        self.series[nuevo["id"]] = [{"periodo_inicio": d, "valor": v} for d, v in puntos]
        return dict(nuevo), True

    def listar(self, disease=None, region=None, regiones=None):
        return [dict(c) for c in reversed(list(self.conjuntos.values()))
                if (regiones is None or c["region_id"] in regiones)
                and (not disease or c["disease"] == disease) and (not region or c["region"] == region)]

    def get(self, dataset_id):
        return dict(self.conjuntos[dataset_id]) if dataset_id in self.conjuntos else None

    def puntos(self, dataset_id):
        return list(self.series[dataset_id])


@pytest.fixture
def base(monkeypatch):
    falsa = Base()
    for nombre in ("ids_de", "guardar", "listar", "get", "puntos"):
        monkeypatch.setattr(datos, nombre, getattr(falsa, nombre))
    return falsa


@pytest.fixture
def cliente(crear_cliente, base):
    return crear_cliente("importacion")


def importar(cliente, cabeceras, cuerpo=CSV, tipo="text/csv", ruta="/api/v1/datasets", **cambios):
    consulta = urlencode({k: v for k, v in dict(META, **cambios).items() if v is not None})
    return cliente.post(ruta + "?" + consulta + "&format=json", data=cuerpo, content_type=tipo, headers=cabeceras)


def test_sin_token_es_401(cliente):
    assert importar(cliente, {}).status_code == 401


@pytest.mark.parametrize("rol", ["CAPTURISTA", "INVESTIGADOR", "AUTORIDAD_SANITARIA"])
def test_quien_no_tiene_datasets_upload_no_importa(cliente, token, base, rol):
    assert importar(cliente, token((rol,))).status_code == 403
    assert base.conjuntos == {}


def test_capturista_no_consulta(cliente, token):
    assert cliente.get("/api/v1/datasets", headers=token(("CAPTURISTA",))).status_code == 403


@pytest.mark.parametrize("rol", ["EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR"])
def test_importa_y_el_mismo_archivo_no_se_duplica(cliente, token, base, rol):
    primera = importar(cliente, token((rol,)))
    assert primera.status_code == 201
    conjunto = primera.get_json()
    assert conjunto["version"] == 1 and conjunto["sha256"] == hashlib.sha256(CSV).hexdigest()
    assert conjunto["resumen"]["total"] == 103 and conjunto["imported_by"] == 7
    otra = importar(cliente, token((rol,)))
    assert otra.status_code == 200 and otra.get_json()["id"] == conjunto["id"]


def test_otro_archivo_con_la_misma_clave_es_la_version_siguiente(cliente, token):
    importar(cliente, token())
    json_ = (CONTRATO / "ejemplos/entrada_serie.json").read_bytes()
    r = importar(cliente, token(), json_, "application/json")
    assert r.status_code == 201 and r.get_json()["version"] == 2


def test_el_xml_tambien_se_importa(cliente, token):
    xml = (CONTRATO / "ejemplos/entrada_serie.xml").read_bytes()
    assert importar(cliente, token(), xml, "application/xml").status_code == 201


def test_validar_no_guarda_y_da_todas_las_fallas(cliente, token, base):
    r = importar(cliente, token(), ruta="/api/v1/datasets/validate")
    assert r.status_code == 200 and r.get_json()["valido"] is True and r.get_json()["resumen"]["puntos"] == 4
    malo = CSV.replace(b"2020-03-15,40", b"2020-03-15,-1")
    r = importar(cliente, token(), malo, ruta="/api/v1/datasets/validate", region="99", license=None)
    datos_ = r.get_json()
    assert r.status_code == 200 and datos_["valido"] is False and datos_["resumen"] is None
    assert datos_["fallas"] == ["Falta license.", "No existe la región 99.", "Línea 5: valor debe ser un entero no negativo."]
    assert base.conjuntos == {}


def test_importar_algo_invalido_es_422_y_no_guarda(cliente, token, base):
    r = importar(cliente, token(), CSV.replace(b"periodo_inicio,valor", b"periodo_inicio,valor,edad"))
    assert r.status_code == 422 and "RNF-I05" in r.get_json()["detail"]
    assert importar(cliente, token(), disease="NADA").status_code == 422
    assert importar(cliente, token(), cutoff="2020-03-21").status_code == 422
    r = importar(cliente, token(), period="mes")
    assert r.status_code == 422 and "period debe ser semana o dia." in r.get_json()["detail"]
    assert base.conjuntos == {}


def test_formato_tamanio_y_archivo_roto(cliente, token):
    assert importar(cliente, token(), b"x", "text/plain").status_code == 415
    assert importar(cliente, token(), b"{roto", "application/json").status_code == 400
    assert importar(cliente, token(), b"0" * (2 * 1024 * 1024 + 1)).status_code == 413


def test_fuera_del_alcance_no_importa_ni_ve(cliente, token, base, alcance_falso):
    assert importar(cliente, token()).status_code == 201
    alcance_falso["regiones"] = [9]
    assert importar(cliente, token(), CSV + b"2020-03-29,3\n").status_code == 403
    assert cliente.get("/api/v1/datasets?format=json", headers=token()).get_json()["total"] == 0
    assert cliente.get("/api/v1/datasets/1?format=json", headers=token()).status_code == 403
    assert cliente.get("/api/v1/datasets/1/points?format=json", headers=token()).status_code == 403


def test_investigador_consulta_y_ve_la_serie(cliente, token):
    importar(cliente, token())
    lector = token(("INVESTIGADOR",))
    lista = cliente.get("/api/v1/datasets?disease=SARS_COV_2_ANCESTRAL&format=json", headers=lector).get_json()
    assert lista["total"] == 1
    assert cliente.get("/api/v1/datasets?region=02&format=json", headers=lector).get_json()["total"] == 0
    assert cliente.get("/api/v1/datasets/1?format=json", headers=lector).get_json()["code"] == META["code"]
    assert cliente.get("/api/v1/datasets/9?format=json", headers=lector).status_code == 404
    serie = cliente.get("/api/v1/datasets/1/points?format=json", headers=lector).get_json()
    assert serie["puntos"][0] == {"periodo_inicio": "2020-03-01", "valor": 7}


def test_la_serie_en_xml_valida_contra_su_xsd_y_se_puede_volver_a_importar(cliente, token):
    importar(cliente, token())
    xml = cliente.get("/api/v1/datasets/1/points", headers=token()).data
    xmlschema.XMLSchema(str(CONTRATO / "serie_observada.xsd")).validate(xml.decode("utf-8"))
    assert importar(cliente, token(), xml, "application/xml", code="OTRA_CLAVE").status_code == 201


@pytest.mark.parametrize("ruta,ejemplo", [("/api/v1/datasets/1", "consultar_conjunto"),
                                          ("/api/v1/datasets", "listar_conjuntos"),
                                          ("/api/v1/datasets/1/points", "puntos_conjunto")])
def test_las_respuestas_traen_las_claves_del_contrato(cliente, token, ruta, ejemplo):
    importar(cliente, token(), source_url=None)
    real = cliente.get(ruta + "?format=json", headers=token()).get_json()
    contrato = json.loads((CONTRATO / "ejemplos" / (ejemplo + ".json")).read_text(encoding="utf-8"))
    assert set(real) == set(contrato)
    if "conjuntos" in real:
        real, contrato = real["conjuntos"][0], contrato["conjuntos"][0]
    if "resumen" in real:
        assert set(real["resumen"]) == set(contrato["resumen"])


def test_validar_trae_las_claves_del_contrato(cliente, token):
    real = importar(cliente, token(), ruta="/api/v1/datasets/validate").get_json()
    contrato = json.loads((CONTRATO / "ejemplos/validar_conjunto.json").read_text(encoding="utf-8"))
    assert set(real) == set(contrato) and set(real["resumen"]) == set(contrato["resumen"])


def test_el_resumen_lleva_fechas_iso(cliente, token):
    r = importar(cliente, token()).get_json()
    assert date.fromisoformat(r["resumen"]["inicio"]) == date(2020, 3, 1)
