"""Campañas de salud (D49): validación, rutas y el aviso a los CAPTURISTA."""
from datetime import date, datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import pytest

from epidemia_comun.errores import ErrorAPI
from microservicios.vacunas import campanas, rutas

# Relativas a hoy: la validación rechaza una campaña que ya terminó.
HOY = date.today()
INICIO, FIN = HOY + timedelta(days=9), HOY + timedelta(days=23)
CAMPANA = {"name": "Vacunación contra influenza 2026", "disease_id": 1, "region_id": 39,
           "starts_on": INICIO.isoformat(), "ends_on": FIN.isoformat(), "target_population": 120000,
           "description": "Adultos de 60 años o más y personas con enfermedades crónicas."}


# ------------------------------------------------------------------ validación

def test_datos_validos():
    limpios = campanas.datos(dict(CAMPANA, name="  Influenza  "), hoy=HOY)
    assert limpios["name"] == "Influenza" and limpios["starts_on"] == INICIO
    assert campanas.datos(dict(CAMPANA, region_id=None, target_population=None, description=""),
                          hoy=HOY)["region_id"] is None


@pytest.mark.parametrize("cambios,mensaje", [
    ({"name": ""}, "name es obligatorio"),
    ({"disease_id": None}, "disease_id es obligatorio"),
    ({"disease_id": "x"}, "disease_id"),
    ({"starts_on": "01/12/2026"}, "starts_on es una fecha"),
    ({"ends_on": (INICIO - timedelta(days=1)).isoformat()}, "anterior a starts_on"),
    ({"starts_on": (HOY - timedelta(days=20)).isoformat(), "ends_on": (HOY - timedelta(days=10)).isoformat()},
     "ya terminó"),
    ({"target_population": 0}, "target_population"),
    ({"target_population": 30000000}, "target_population"),
    ({"description": "x" * 2001}, "2000"),
    ({"otro": 1}, "no reconocidos"),
])
def test_datos_invalidos_son_422(cambios, mensaje):
    with pytest.raises(ErrorAPI) as error:
        campanas.datos(dict(CAMPANA, **cambios), hoy=HOY)
    assert error.value.estado == 422 and mensaje in error.value.detalle


def test_el_motivo_de_cancelar():
    assert campanas.motivo({"reason": " Sin vacunas "}) == "Sin vacunas"
    for cuerpo in ({}, {"reason": ""}, {"reason": "x" * 501}, {"reason": "x", "otro": 1}):
        with pytest.raises(ErrorAPI):
            campanas.motivo(cuerpo)


# ------------------------------------------------------------------ rutas

class Almacen:
    """campaigns en memoria, con el estado calculado como en la base (hoy fijo)."""

    def __init__(self):
        self.filas = {}

    def estado(self, f):
        if f["cancelled_at"]:
            return "cancelada"
        return "programada" if HOY < f["starts_on"] else "terminada" if HOY > f["ends_on"] else "activa"

    def salida(self, f):
        return dict(f, status=self.estado(f), enfermedad="Influenza estacional",
                    municipio="Monterrey" if f["region_id"] else "Nuevo León")

    def crea(self, limpios, usuario):
        nuevo = len(self.filas) + 1
        self.filas[nuevo] = dict(limpios, id=nuevo, created_by=usuario,
                                 created_at=datetime(2026, 11, 22, tzinfo=timezone.utc), updated_at=None,
                                 cancelled_at=None, cancelled_by=None, cancel_reason=None)
        return self.salida(self.filas[nuevo])

    def por_id(self, campana_id):
        return self.salida(self.filas[campana_id]) if campana_id in self.filas else None

    def lista(self, estado=None, disease_id=None, region_id=None, limite=50):
        filas = [self.salida(f) for f in self.filas.values()]
        return [f for f in filas if estado in (None, f["status"])][:limite]

    def _editable(self, campana_id):
        if campana_id not in self.filas:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la campaña.")
        if self.estado(self.filas[campana_id]) in ("cancelada", "terminada"):
            raise ErrorAPI(409, "CONFLICTO", "La campaña ya está %s." % self.estado(self.filas[campana_id]))

    def actualiza(self, campana_id, limpios):
        self._editable(campana_id)
        self.filas[campana_id].update(limpios)
        return self.por_id(campana_id)

    def cancela(self, campana_id, razon, usuario):
        self._editable(campana_id)
        self.filas[campana_id].update(cancelled_at=datetime(2026, 11, 23, tzinfo=timezone.utc),
                                      cancelled_by=usuario, cancel_reason=razon)
        return self.por_id(campana_id)


@pytest.fixture
def almacen(monkeypatch):
    a = Almacen()
    for nombre in ("crea", "por_id", "lista", "actualiza", "cancela"):
        monkeypatch.setattr(campanas, nombre, getattr(a, nombre))

    def verifica(disease_id, region_id):
        if disease_id != 1 or region_id not in (None, 39):
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe.")
    monkeypatch.setattr(campanas, "verifica_catalogos", verifica)
    return a


@pytest.fixture
def avisos(monkeypatch):
    enviados = []

    class Resp:
        status_code = 201

    monkeypatch.setattr(rutas, "llamar", lambda servicio, metodo, ruta, **kw: enviados.append(kw["cuerpo"]) or Resp())
    monkeypatch.setattr(rutas, "log_audit", lambda *a, **k: None)
    return enviados


@pytest.fixture
def cliente(crear_cliente, almacen, avisos):
    return crear_cliente("vacunas")


@pytest.fixture
def epi(token):
    return token(roles=("EPIDEMIOLOGO",), sub="9")


def test_crear_avisa_a_los_capturistas(cliente, epi, avisos):
    r = cliente.post("/api/v1/campaigns?format=json", json=CAMPANA, headers=epi)
    assert r.status_code == 201, r.get_json()
    nueva = r.get_json()
    assert (nueva["status"], nueva["municipio"]) == ("programada", "Monterrey")
    (aviso,) = avisos
    assert (aviso["role"], aviso["type"]) == ("CAPTURISTA", "CAMPAIGN")
    assert aviso["title"] == "Campaña: Vacunación contra influenza 2026"
    assert aviso["body"] == "Influenza estacional, del %s al %s, en Monterrey." % (INICIO, FIN)
    assert aviso["payload"]["campaign_id"] == 1


def test_editar_y_cancelar(cliente, epi, avisos, almacen):
    cliente.post("/api/v1/campaigns?format=json", json=CAMPANA, headers=epi)
    r = cliente.put("/api/v1/campaigns/1?format=json", json=dict(CAMPANA, region_id=None), headers=epi)
    assert r.status_code == 200 and r.get_json()["municipio"] == "Nuevo León"
    r = cliente.post("/api/v1/campaigns/1/cancel?format=json", json={"reason": "No llegaron las vacunas"},
                     headers=epi)
    assert r.status_code == 200 and r.get_json()["status"] == "cancelada"
    assert avisos[-1]["title"] == "Se canceló la campaña: Vacunación contra influenza 2026"
    assert cliente.post("/api/v1/campaigns/1/cancel?format=json", json={"reason": "x"},
                        headers=epi).status_code == 409
    assert cliente.put("/api/v1/campaigns/1?format=json", json=CAMPANA, headers=epi).status_code == 409


def test_lista_y_consulta_para_los_cuatro_roles(cliente, epi, token):
    cliente.post("/api/v1/campaigns?format=json", json=CAMPANA, headers=epi)
    for rol in ("CAPTURISTA", "ANALISTA", "ADMINISTRADOR"):
        cabeceras = token(roles=(rol,))
        assert cliente.get("/api/v1/campaigns?format=json", headers=cabeceras).get_json()["total"] == 1
        assert cliente.get("/api/v1/campaigns/1?format=json", headers=cabeceras).status_code == 200
    assert cliente.get("/api/v1/campaigns?status=activa&format=json", headers=epi).get_json()["total"] == 0


@pytest.mark.parametrize("roles", [("CAPTURISTA",), ("ANALISTA",)])
def test_solo_epidemiologo_y_administrador_las_crean(cliente, token, roles):
    assert cliente.post("/api/v1/campaigns?format=json", json=CAMPANA, headers=token(roles=roles)).status_code == 403


@pytest.mark.parametrize("cambios,estado", [({"disease_id": 7}, 404), ({"region_id": 5}, 404), ({"name": ""}, 422)])
def test_alta_invalida(cliente, epi, cambios, estado):
    assert cliente.post("/api/v1/campaigns?format=json", json=dict(CAMPANA, **cambios), headers=epi).status_code == estado


def test_consultas_invalidas(cliente, epi):
    assert cliente.get("/api/v1/campaigns/9?format=json", headers=epi).status_code == 404
    assert cliente.get("/api/v1/campaigns?status=vieja&format=json", headers=epi).status_code == 422
    assert cliente.get("/api/v1/campaigns?limit=500&format=json", headers=epi).status_code == 422


def test_campanas_en_xml(cliente, epi):
    cliente.post("/api/v1/campaigns?format=json", json=CAMPANA, headers=epi)
    raiz = ET.fromstring(cliente.get("/api/v1/campaigns", headers=epi).data)
    assert raiz.tag == "campanas" and raiz.find("campanas/campana").findtext("name") == CAMPANA["name"]


def test_si_notificaciones_falla_la_campana_se_queda(cliente, epi, almacen, monkeypatch):
    def falla(*a, **k):
        raise RuntimeError("caído")
    monkeypatch.setattr(rutas, "llamar", falla)
    assert cliente.post("/api/v1/campaigns?format=json", json=CAMPANA, headers=epi).status_code == 201
    assert len(almacen.filas) == 1
