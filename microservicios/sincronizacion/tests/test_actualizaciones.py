"""Correcciones hechas sin conexión en el lote de sincronización (D47): nunca se sobrescribe en
silencio lo que cambió otra persona."""
from xml.etree import ElementTree as ET

import pytest

from epidemia_comun.errores import ErrorAPI
from microservicios.sincronizacion import rutas
from microservicios.sincronizacion.tests.test_sincronizacion import (  # noqa: F401
    LOTE, U1, Resp, bitacora, captura)


class CasosConVersion:
    """Imita a casos: GET y PATCH /cases/{id} con If-Match, y POST /cases/batch."""

    def __init__(self):
        self.casos = {5: {"id": 5, "version": 1, "age": 30, "severity": "leve", "status": "pendiente"},
                      6: {"id": 6, "version": 3, "age": 50, "severity": "grave", "status": "validado"}}
        self.parches = []
        self.respuesta_fija = None
        self.avisos = []

    def __call__(self, servicio, metodo, ruta, formato="json", cuerpo=None, token=None,
                 cabeceras=None, **kw):
        if servicio == "notificaciones":
            self.avisos.append(cuerpo)
            return Resp(201, {})
        if ruta.endswith("/batch"):
            return Resp(200, {"total": len(cuerpo["cases"]), "resultados": [
                {"indice": i, "estado": 201, "caso": {"id": 100 + i}} for i in range(len(cuerpo["cases"]))]})
        case_id = int(ruta.rsplit("/", 1)[1])
        caso = self.casos.get(case_id)
        if metodo == "GET":
            return Resp(200, dict(caso)) if caso else Resp(404, {"codigo": "NO_ENCONTRADO", "detail": "No existe el caso."})
        self.parches.append((case_id, cabeceras, cuerpo))
        if self.respuesta_fija:
            return self.respuesta_fija
        if caso is None:
            return Resp(404, {"codigo": "NO_ENCONTRADO", "detail": "No existe el caso."})
        if caso["status"] != "pendiente":
            return Resp(403, {"codigo": "PERMISO_INSUFICIENTE",
                              "detail": "Solo puedes corregir tus casos mientras están pendientes."})
        if int(cabeceras["If-Match"].strip('"')) != caso["version"]:
            return Resp(412, {"codigo": "CONFLICTO", "detail": "El caso cambió desde que lo leíste."})
        cambios = {k: v for k, v in cuerpo.items() if k not in ("reason", "device_id")}
        if any(caso.get(k) != v for k, v in cambios.items()):
            caso.update(cambios)
            caso["version"] += 1
        return Resp(200, dict(caso))


@pytest.fixture
def casos(monkeypatch):
    falso = CasosConVersion()
    monkeypatch.setattr(rutas, "llamar", falso)
    return falso


@pytest.fixture
def cliente(crear_cliente, casos, bitacora):
    return crear_cliente("sincronizacion")


def envia(cliente, captura, **lote):
    lote.setdefault("batch_id", LOTE)
    return cliente.post("/api/v1/sync/cases?format=json", json=lote, headers=captura)


def correccion(case_id=5, version=1, **cambios):
    return {"case_id": case_id, "version": version, "changes": cambios or {"age": 31},
            "reason": "Edad mal capturada"}


def test_una_correccion_con_la_version_vigente_se_aplica(cliente, captura, casos, bitacora):
    r = envia(cliente, captura, device_id=3, updates=[correccion()])
    assert r.status_code == 200
    datos = r.get_json()
    assert (datos["total"], datos["actualizados"], datos["conflictos"]) == (0, 1, 0)
    (hecha,) = datos["actualizaciones"]
    assert (hecha["case_id"], hecha["resultado"], hecha["version"]) == (5, "actualizado", 2)
    ((case_id, cabeceras, cuerpo),) = casos.parches
    assert cabeceras == {"If-Match": '"1"'}
    assert cuerpo == {"age": 31, "reason": "Edad mal capturada", "device_id": 3}
    assert bitacora[-1][4]["actualizados"] == 1


def test_si_otro_la_cambio_regresa_conflicto_con_el_caso_actual(cliente, captura, casos):
    casos.casos[5].update(version=2, age=33)  # otro profesional ya lo corrigió
    datos = envia(cliente, captura, updates=[correccion(version=1, age=31)]).get_json()
    (hecha,) = datos["actualizaciones"]
    assert (hecha["resultado"], hecha["codigo"], hecha["version"]) == ("conflicto", "CONFLICTO", 2)
    assert hecha["caso"]["age"] == 33 and datos["conflictos"] == 1
    assert casos.casos[5]["age"] == 33  # no se sobrescribió


def test_reenviar_un_lote_que_fallo_a_medias_no_es_conflicto(cliente, captura, casos):
    # La corrección ya entró (versión 2 con edad 31), pero el lote no se guardó: se reenvía.
    casos.casos[5].update(version=2, age=31)
    (hecha,) = envia(cliente, captura, updates=[correccion(version=1, age=31)]).get_json()["actualizaciones"]
    assert (hecha["resultado"], hecha["version"]) == ("actualizado", 2)


def test_un_lote_repetido_regresa_lo_guardado_sin_volver_a_corregir(cliente, captura, casos):
    envia(cliente, captura, updates=[correccion()])
    r = envia(cliente, captura, updates=[correccion()])
    assert r.get_json()["repetido"] is True and len(casos.parches) == 1


def test_una_correccion_que_casos_no_permite_sale_rechazada(cliente, captura, casos):
    datos = envia(cliente, captura, updates=[correccion(case_id=6, version=3), correccion(case_id=77)]).get_json()
    assert [(h["resultado"], h["codigo"]) for h in datos["actualizaciones"]] == [
        ("rechazado", "PERMISO_INSUFICIENTE"), ("rechazado", "NO_ENCONTRADO")]
    assert datos["actualizaciones_rechazadas"] == 2


def test_casos_nuevos_y_correcciones_en_el_mismo_lote(cliente, captura, casos):
    nuevo = {"local_uuid": U1, "disease_id": 1, "region_id": 10, "report_date": "2026-10-01"}
    datos = envia(cliente, captura, cases=[nuevo], updates=[correccion()]).get_json()
    assert (datos["creados"], datos["actualizados"]) == (1, 1)


def test_un_lote_sin_correcciones_no_trae_esos_campos(cliente, captura, casos):
    nuevo = {"local_uuid": U1, "disease_id": 1, "region_id": 10, "report_date": "2026-10-01"}
    datos = envia(cliente, captura, cases=[nuevo]).get_json()
    assert "actualizaciones" not in datos and "conflictos" not in datos


@pytest.mark.parametrize("updates", [
    [{"case_id": 5, "version": 1}],
    [{"case_id": 5, "version": 1, "changes": {}}],
    [{"case_id": "x", "version": 1, "changes": {"age": 31}}],
    [{"case_id": 5, "version": 0, "changes": {"age": 31}}],
    [{"case_id": 5, "version": 1, "changes": {"age": 31}, "otro": 1}],
    [{"case_id": 5, "version": 1, "changes": {"age": 31}, "reason": 3}],
    "no es lista",
])
def test_correcciones_invalidas_son_422(cliente, captura, casos, updates):
    assert envia(cliente, captura, updates=updates).status_code == 422


def test_un_lote_sin_casos_ni_correcciones_es_422(cliente, captura):
    assert envia(cliente, captura).status_code == 422


def test_mas_de_100_entre_casos_y_correcciones_es_422(cliente, captura):
    nuevos = [{"local_uuid": "%08d-1111-4111-8111-111111111111" % i, "disease_id": 1,
               "region_id": 10, "report_date": "2026-10-01"} for i in range(60)]
    r = envia(cliente, captura, cases=nuevos, updates=[correccion(case_id=i) for i in range(1, 42)])
    assert r.status_code == 422


@pytest.mark.parametrize("estado,esperado", [(401, 401), (429, 429), (500, 503)])
def test_si_casos_falla_todo_el_lote_falla(cliente, captura, casos, estado, esperado):
    casos.respuesta_fija = Resp(estado, {"codigo": "X", "detail": "falla"})
    casos.respuesta_fija.headers = {"Retry-After": "7"}
    r = envia(cliente, captura, updates=[correccion()])
    assert r.status_code == esperado
    if esperado == 429:
        assert r.headers["Retry-After"] == "7"


def test_correcciones_en_xml(cliente, captura, casos):
    xml = ("<lote><batch_id>%s</batch_id><updates><item><case_id>5</case_id><version>1</version>"
           "<changes><age>31</age></changes><reason>Edad</reason></item></updates></lote>" % LOTE)
    r = cliente.post("/api/v1/sync/cases", data=xml,
                     headers=dict(captura, **{"Content-Type": "application/xml"}))
    assert r.status_code == 200
    raiz = ET.fromstring(r.data)
    assert raiz.findtext("actualizados") == "1"
    assert raiz.find("actualizaciones/item").findtext("resultado") == "actualizado"
