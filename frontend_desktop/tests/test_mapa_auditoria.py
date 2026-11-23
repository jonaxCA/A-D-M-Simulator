import json
import os
from pathlib import Path

import pytest

from frontend_desktop.app import api, config, servicios, xmlio
from frontend_desktop.tests.test_api import Respuesta, cliente, problema, sesion


class GeoRespuesta(Respuesta):
    def json(self):
        return json.loads(self.content)


def test_geojson_negocia_formato_conserva_etag_y_renueva_turno():
    contenido = b'{"type":"FeatureCollection","features":[]}'
    geo = GeoRespuesta(200, contenido, {"ETag": '"v1"', "Content-Type": "application/geo+json; charset=utf-8"})
    c = cliente(geo, problema(401, "TOKEN_EXPIRADO"), sesion("nuevo", "renovacion"), Respuesta(304))
    assert servicios.geometria_municipal(c)[1] == '"v1"'
    assert servicios.geometria_municipal(c, '"v1"') == (None, '"v1"')
    cabeceras = c.http.llamadas[-1][3]
    assert cabeceras["Authorization"] == "Bearer nuevo"
    assert cabeceras["If-None-Match"] == '"v1"'
    assert cabeceras["Accept"] == "application/geo+json"
    assert c.http.llamadas[-2][3]["Accept"] == "application/xml"


def test_geojson_rechaza_el_formato_inesperado():
    c = cliente(Respuesta(200, b"<!doctype html>", {"Content-Type": "text/html"}))
    with pytest.raises(api.ErrorServicio, match="GeoJSON válida"):
        servicios.geometria_municipal(c)


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF
from PySide6.QtWidgets import QApplication

from frontend_desktop.app.ui.auditoria import DialogoAuditoria
from frontend_desktop.app.ui.mapa import MapaMunicipal, NIVELES
from frontend_desktop.app.ui.validacion_modelo import DialogoValidacionModelo
from frontend_desktop.app.ui.zonas import DialogoZonas
from frontend_desktop.tests.test_humo import esperar


@pytest.fixture
def qt():
    app = QApplication.instance() or QApplication([])
    widgets = []
    yield app, widgets
    esperar(app)
    for widget in widgets:
        widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class Ventana:
    def __init__(self, cliente):
        self.cliente = cliente
        self.errores = []

    def mostrar_error(self, exc):
        self.errores.append(exc)


def ejemplo(servicio, nombre):
    return xmlio.leer((config.CONTRATOS / servicio / "ejemplos" / (nombre + ".xml")).read_bytes())


def test_mapa_usa_geometria_inegi_y_carga_la_serie_al_elegir(qt, monkeypatch):
    app, widgets = qt
    ruta = Path(__file__).resolve().parents[2] / "datos/geo/nl_municipios.geojson"
    geo = json.loads(ruta.read_text(encoding="utf-8"))
    llamadas = []
    datos = ejemplo("zonas", "datos_mapa")
    monkeypatch.setattr(servicios, "zonas_mapa", lambda *_: datos)

    def geometria(_, etag):
        llamadas.append(etag)
        return (None if etag else geo), '"v1"'

    monkeypatch.setattr(servicios, "geometria_municipal", geometria)
    vista = DialogoZonas(None, Ventana(object()), 2, "Ejemplo de contrato")
    widgets.append(vista)
    esperar(app)
    assert len(vista.poligonos.poligonos) == 51
    assert "INEGI" in vista.fuente.text()
    assert vista.poligonos.poligonos["19002"].brush().color().name() == NIVELES["baja"][1].lower()
    assert vista.poligonos.poligonos["19051"].brush().color().name() == NIVELES["sin dato"][1].lower()
    vista.poligonos.municipio.emit("19002")
    assert vista.tabla.currentItem().text() == "Agualeguas"
    assert "Agualeguas" in vista.encabezado_serie.text()
    vista.periodo.setCurrentIndex(1)
    esperar(app)
    assert llamadas == [None, '"v1"']
    assert len(vista.poligonos.poligonos) == 51


def test_mapa_respeta_huecos_y_multipoligonos(qt):
    _, widgets = qt
    mapa = MapaMunicipal()
    widgets.append(mapa)
    exterior = [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]
    hueco = [(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)]
    isla = [(8, 0), (9, 0), (9, 1), (8, 1), (8, 0)]
    mapa.poner({"features": [{"properties": {"region_code": "1", "name": "Municipio"},
                             "geometry": {"type": "MultiPolygon", "coordinates": [[exterior, hueco], [isla]]}}]}, [])
    camino = mapa.poligonos["1"].path()
    assert camino.contains(QPointF(0.2, -0.2))
    assert not camino.contains(QPointF(1.8, -2))
    assert camino.contains(QPointF(7.7, -0.5))


def test_auditoria_por_entidad_pagina_y_respeta_403(qt):
    app, widgets = qt
    llamadas = []

    class Cliente:
        def pedir(self, servicio, metodo, ruta, params=None):
            llamadas.append((servicio, metodo, ruta, params))
            if ruta == "/api/v1/scenarios/12":
                assert params == {"version": 1}
                return {"version": {"id": 31, "version_number": 1}}
            if ruta.endswith("/scenario_interventions/7"):
                raise api.ErrorServicio("Fuera de alcance", 403)
            offset = params["offset"]
            evento = {"id": 340, "fecha": "2026-11-18T12:05:00+00:00", "usuario": "Eva",
                      "accion": "UPDATE", "antes": {"status": "en_revision"}, "datos": {"status": "aprobado"}}
            total = 51 if "/scenarios/" in ruta else 1
            return xmlio.leer(xmlio.escribir({"offset": offset, "coincidencias": total,
                              "eventos": [evento] * (min(50, total) if offset == 0 else 1)}, "bitacora"))

    ventana = Ventana(Cliente())
    escenario = {"id": 12, "name": "Prueba", "version": {"id": 33, "version_number": 2},
                 "intervenciones": [{"id": 7, "name": "Ejemplo"}]}
    dialogo = DialogoAuditoria(None, ventana, escenario, [{"version_number": 1}, {"version_number": 2}])
    widgets.append(dialogo)
    esperar(app)
    assert dialogo.tabla.item(0, 2).text() == "Aprobación (UPDATE)"
    assert '"status": "en_revision"' in dialogo.detalle.toPlainText()
    dialogo.siguiente.click()
    esperar(app)
    assert llamadas[-1][-1] == {"limit": 50, "offset": 50} and dialogo.tabla.rowCount() == 1
    dialogo.entidad.setCurrentIndex(2)
    esperar(app)
    assert llamadas[-1][2] == "/api/v1/audit/history/scenario_versions/31"
    dialogo.entidad.setCurrentIndex(3)
    esperar(app)
    assert "no tiene acceso" in dialogo.estado.text() and dialogo.tabla.rowCount() == 0
    assert not ventana.errores


def test_validacion_consumida_por_contrato_y_solo_version_aprobada(qt):
    app, widgets = qt
    llamadas = []

    class Cliente:
        def pedir(self, servicio, metodo, ruta, params=None):
            llamadas.append((servicio, metodo, ruta, params))
            if ruta.endswith("/calibration"):
                assert params == {"disease": 2, "region": 3}
                return ejemplo("pareto", "consultar_calibracion")
            assert params == {"version": 7, "parameter": "r0", "percent": "-10,10"}
            return ejemplo("pareto", "consultar_sensibilidad")

    escenario = {"disease_id": 2, "region_id": 3, "version": {"id": 7, "status": "borrador"}}
    ventana = Ventana(Cliente())
    borrador = DialogoValidacionModelo(None, ventana, escenario)
    aprobado = DialogoValidacionModelo(None, ventana, dict(escenario, version={"id": 7, "status": "aprobado"}))
    widgets.extend([borrador, aprobado])
    esperar(app)
    assert not borrador.calcular.isEnabled()
    assert aprobado.modelos.item(0, 1).text() == "sin_calibrar"
    aprobado.cambios.setText("-10,10")
    aprobado.calcular.click()
    esperar(app)
    assert aprobado.filas.rowCount() == 3 and "exploratoria" in aprobado.nota.text()
    assert llamadas[-1][2].endswith("/sensitivity") and not ventana.errores
