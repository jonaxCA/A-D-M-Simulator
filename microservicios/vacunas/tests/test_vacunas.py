from datetime import date, datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from backend_web import vacunas
from microservicios.vacunas import rutas

RAIZ = Path(__file__).resolve().parents[3]
CONTRATO = RAIZ / "docs/contratos/vacunas"
LOTE = {"lot_code": "FL3239-2026", "disease_id": 1, "doses_total": 10, "expires_on": "2027-03-31"}


def lote(lote_id, codigo, total=10, usadas=0, vencido=False):
    return {"id": lote_id, "lot_code": codigo, "manufacturer": None, "disease_id": 1,
            "disease_name": "Influenza A", "region_id": None, "region_name": None,
            "doses_total": total, "doses_used": usadas, "doses_remaining": total - usadas,
            "expires_on": date(2027, 3, 31), "vencido": vencido, "scanned_by": 7,
            "scanned_at": datetime(2026, 11, 1, 18, tzinfo=timezone.utc)}


class Mundo:
    """backend_web.vacunas simulado; valida_lote es la real."""

    def __init__(self):
        self.lotes = {5: lote(5, "EW0153"), 6: lote(6, "VIEJO-1", vencido=True)}
        self.altas, self.aplicadas, self.listados = [], [], []
        self.conflicto = None

    def registrar_lote(self, datos, user_id, *, contexto):
        self.altas.append((datos, user_id, contexto.user_id))
        if self.conflicto:
            return None, False, self.conflicto
        previo = next((l for l in self.lotes.values() if l["lot_code"] == datos["lot_code"]), None)
        if previo:
            return dict(previo), False, None
        nuevo = lote(len(self.lotes) + 10, datos["lot_code"], datos["doses_total"])
        self.lotes[nuevo["id"]] = nuevo
        return dict(nuevo), True, None

    def aplicar_dosis(self, lote_id, dosis, *, contexto):
        self.aplicadas.append((lote_id, dosis, contexto.user_id))
        actual = self.lotes.get(lote_id)
        if actual is None:
            return None, "No existe el lote."
        if actual["vencido"]:
            return None, "El lote caducó el 2026-10-15: ya no se le aplican dosis."
        if dosis > actual["doses_remaining"]:
            return None, "Al lote le quedan %d dosis." % actual["doses_remaining"]
        actual.update(doses_used=actual["doses_used"] + dosis,
                      doses_remaining=actual["doses_remaining"] - dosis)
        return dict(actual), None

    def listar_lotes(self, lot_code=None, disease_id=None, region_id=None, limite=50):
        self.listados.append({"lot_code": lot_code, "disease_id": disease_id,
                              "region_id": region_id, "limite": limite})
        return [dict(l) for l in self.lotes.values() if lot_code in (None, l["lot_code"])]

    def get_lote(self, lote_id):
        return dict(self.lotes[lote_id]) if lote_id in self.lotes else None


@pytest.fixture
def mundo(monkeypatch):
    m = Mundo()
    for nombre in ("registrar_lote", "aplicar_dosis", "listar_lotes", "get_lote"):
        monkeypatch.setattr(vacunas, nombre, getattr(m, nombre))
    return m


@pytest.fixture
def cliente(crear_cliente, mundo):
    return crear_cliente("vacunas")


@pytest.fixture
def capturista(token):
    return token(("CAPTURISTA",))


def post(cliente, ruta, cabeceras, cuerpo):
    return cliente.post(ruta + "?format=json", json=cuerpo, headers=cabeceras)


# ---- registrar ------------------------------------------------------------------------

def test_sin_token_es_401(cliente):
    assert cliente.post("/api/v1/vaccine-lots", json=LOTE).status_code == 401


@pytest.mark.parametrize("rol", ["ANALISTA", "EPIDEMIOLOGO"])
def test_quien_no_captura_no_registra_ni_aplica(cliente, token, mundo, rol):
    assert post(cliente, "/api/v1/vaccine-lots", token((rol,)), LOTE).status_code == 403
    assert post(cliente, "/api/v1/vaccine-lots/5/doses", token((rol,)), {"doses": 1}).status_code == 403
    assert mundo.altas == mundo.aplicadas == []


@pytest.mark.parametrize("rol", rutas.ROLES_ESCRIBEN)
def test_registrar_uno_nuevo_y_el_reintento(cliente, token, mundo, rol):
    r = post(cliente, "/api/v1/vaccine-lots", token((rol,)), LOTE)
    assert r.status_code == 201 and r.get_json()["lot_code"] == "FL3239-2026"
    datos, usuario, _ = mundo.altas[0]
    assert usuario == 7 and datos["expires_on"] == date(2027, 3, 31) and datos["region_id"] is None
    assert post(cliente, "/api/v1/vaccine-lots", token((rol,)), LOTE).status_code == 200


def test_acepta_xml_sin_tipos(cliente, capturista, mundo):
    cuerpo = b"<solicitud><lot_code>XML-1</lot_code><disease_id>1</disease_id>" \
             b"<doses_total>20</doses_total></solicitud>"
    r = cliente.post("/api/v1/vaccine-lots", data=cuerpo, headers=capturista,
                     content_type="application/xml")
    assert r.status_code == 201 and r.mimetype == "application/xml"
    assert ET.fromstring(r.data).findtext("doses_total") == "20"


def test_conflicto_es_409(cliente, capturista, mundo):
    mundo.conflicto = "El lote FL3239-2026 ya está registrado con otros datos; consúltalo por su código."
    r = post(cliente, "/api/v1/vaccine-lots", capturista, LOTE)
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"


@pytest.mark.parametrize("cambio", [{"lot_code": ""}, {"lot_code": "con espacio"}, {"disease_id": "x"},
                                    {"doses_total": 0}, {"expires_on": "31/03/2027"}, {"qr": "crudo"}])
def test_cuerpo_invalido_es_422(cliente, capturista, mundo, cambio):
    r = post(cliente, "/api/v1/vaccine-lots", capturista, dict(LOTE, **cambio))
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert mundo.altas == []


# ---- buscar ---------------------------------------------------------------------------

@pytest.mark.parametrize("rol", rutas.ROLES_LEEN)
def test_despues_de_escanear_se_busca_por_codigo(cliente, token, mundo, rol):
    r = cliente.get("/api/v1/vaccine-lots?format=json&lot_code=%20EW0153", headers=token((rol,)))
    assert r.status_code == 200 and [l["id"] for l in r.get_json()["lotes"]] == [5]
    assert mundo.listados[-1]["lot_code"] == "EW0153"
    r = cliente.get("/api/v1/vaccine-lots?format=json&lot_code=NO-ESTA", headers=token((rol,)))
    assert r.get_json()["total"] == 0


def test_filtros_y_lista_en_xml(cliente, capturista, mundo):
    raiz = ET.fromstring(cliente.get("/api/v1/vaccine-lots?disease_id=1&region_id=39&limit=5",
                                     headers=capturista).data)
    assert raiz.tag == "listado" and len(raiz.findall("lotes/lote")) == 2
    assert mundo.listados == [{"lot_code": None, "disease_id": 1, "region_id": 39, "limite": 5}]


@pytest.mark.parametrize("consulta", ["limit=0", "limit=%d" % (rutas.LIMITE_MAX + 1), "disease_id=x",
                                      "region_id=0"])
def test_filtro_invalido_es_422(cliente, capturista, consulta):
    assert cliente.get("/api/v1/vaccine-lots?" + consulta, headers=capturista).status_code == 422


def test_consultar_uno(cliente, capturista):
    assert cliente.get("/api/v1/vaccine-lots/5", headers=capturista).status_code == 200
    assert cliente.get("/api/v1/vaccine-lots/99", headers=capturista).status_code == 404
    assert cliente.get("/api/v1/vaccine-lots/x", headers=capturista).status_code == 422


# ---- aplicar dosis --------------------------------------------------------------------

def test_aplicar_descuenta(cliente, capturista, mundo):
    r = post(cliente, "/api/v1/vaccine-lots/5/doses", capturista, {"doses": 3})
    assert r.status_code == 200 and r.get_json()["doses_remaining"] == 7
    assert mundo.aplicadas == [(5, 3, 7)]


def test_sin_dosis_suficientes_o_caducado_es_409(cliente, capturista):
    r = post(cliente, "/api/v1/vaccine-lots/5/doses", capturista, {"doses": 11})
    assert r.status_code == 409 and r.get_json()["detail"] == "Al lote le quedan 10 dosis."
    r = post(cliente, "/api/v1/vaccine-lots/6/doses", capturista, {"doses": 1})
    assert r.status_code == 409 and "caducó" in r.get_json()["detail"]
    assert post(cliente, "/api/v1/vaccine-lots/99/doses", capturista, {"doses": 1}).status_code == 404


@pytest.mark.parametrize("cuerpo", [{}, {"doses": 0}, {"doses": True}, {"doses": "x"},
                                    {"doses": vacunas.APLICAR_MAX + 1}, {"doses": 1, "case_id": 3}])
def test_dosis_invalidas_es_422(cliente, capturista, mundo, cuerpo):
    assert post(cliente, "/api/v1/vaccine-lots/5/doses", capturista, cuerpo).status_code == 422
    assert mundo.aplicadas == []


def test_las_peticiones_de_ejemplo_se_aceptan(cliente, capturista, mundo):
    mundo.lotes[5] = lote(5, "EW0153", total=500)
    for op, ruta in (("registrar_lote", "/api/v1/vaccine-lots"), ("aplicar_dosis", "/api/v1/vaccine-lots/5/doses")):
        for ext, tipo in (("json", "application/json"), ("xml", "application/xml")):
            datos = (CONTRATO / "ejemplos" / ("%s.peticion.%s" % (op, ext))).read_bytes()
            r = cliente.post(ruta + "?format=json", data=datos, headers=capturista, content_type=tipo)
            assert r.status_code in (200, 201), (op, ext, r.data)


def test_redis_caido_es_503(cliente, capturista, apagar_redis):
    apagar_redis()
    assert cliente.get("/api/v1/vaccine-lots", headers=capturista).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (CONTRATO / "openapi.json").read_bytes()
