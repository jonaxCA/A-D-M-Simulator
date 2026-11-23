"""importacion de punta a punta (D53): la serie de D50 ya viene en la 061; un ANALISTA importa
una serie agregada, el reintento no la duplica, otra versión de la misma clave sube de número, la
CAPTURISTA no importa ni consulta, y la serie regresa igual que como entró. La base no deja que
svc_importacion edite ni borre un conjunto (D52)."""
import uuid
from pathlib import Path

import psycopg2
import pytest

CSV = (Path(__file__).resolve().parents[3] / "docs/contratos/importacion/ejemplos/entrada_serie.csv").read_bytes()


def _importa(api, cuenta, code, cuerpo=CSV):
    params = {"code": code, "name": "Serie de prueba", "disease": "SARS_COV_2_ANCESTRAL", "region": "19",
              "metric": "casos_confirmados", "period": "semana", "source": "Prueba de integración",
              "license": "Datos abiertos", "cutoff": "2021-10-31"}
    return api("importacion", "POST", "/api/v1/datasets", cuenta["access"], params=params, data=cuerpo,
               headers={"Content-Type": "text/csv"})


def test_una_serie_de_principio_a_fin(api, sesion, base):
    analista, karla = sesion("analista"), sesion("capturista")
    lista = api("importacion", "GET", "/api/v1/datasets", analista["access"], params={"region": "19"}).json()
    assert "COVID19_NL_2020_SINTOMAS" in {c["code"] for c in lista["conjuntos"]}

    code = "PRUEBA_" + uuid.uuid4().hex[:10].upper()
    r = _importa(api, analista, code)
    assert r.status_code == 201, r.text
    conjunto = r.json()
    assert (conjunto["version"], conjunto["resumen"]["total"]) == (1, 103)
    assert _importa(api, analista, code).status_code == 200
    assert _importa(api, analista, code, CSV + b"2020-03-29,5\n").json()["version"] == 2
    assert _importa(api, karla, code).status_code == 403
    assert api("importacion", "GET", "/api/v1/datasets", karla["access"]).status_code == 403

    serie = api("importacion", "GET", "/api/v1/datasets/%d/points" % conjunto["id"], analista["access"]).json()
    assert [(p["periodo_inicio"], p["valor"]) for p in serie["puntos"]][:2] == [("2020-03-01", 7), ("2020-03-08", 38)]

    with base("importacion") as conn, conn.cursor() as cur:
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM observed_datasets WHERE id = %s", (conjunto["id"],))
