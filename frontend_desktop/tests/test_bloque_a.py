import csv
import os

import pytest

from frontend_desktop.app import config, exportar, resumen, servicios, xmlio

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QTableWidget

from frontend_desktop.app.ui import escenarios, simulaciones
from frontend_desktop.app.ui.comparacion import VistaComparacion
from frontend_desktop.app.ui.formularios import FormIntervencion, mostrar_parametros
from frontend_desktop.app.ui.zonas import DialogoZonas
from frontend_desktop.tests.test_humo import ClienteDeEjemplos, Respuesta, datos_comparacion, esperar


def ejemplo(servicio, archivo):
    return (config.CONTRATOS / servicio / "ejemplos" / (archivo + ".xml")).read_bytes()


@pytest.fixture
def qt():
    app = QApplication.instance() or QApplication([])
    ventanas = []
    yield app, ventanas
    esperar(app)
    for ventana in ventanas:
        ventana.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_diferencias_y_exportaciones_usan_referencia_explicita(qt, tmp_path):
    datos = datos_comparacion()
    base, otro = datos["escenarios"]
    base["indicadores"]["fallecimientos"]["mediana"] = 0
    base["indicadores"]["tasa_ataque"]["mediana"] = 0.2
    otro["indicadores"]["tasa_ataque"]["mediana"] = 0.4
    base["costo_pesos"] = None
    otro["costo_pesos"] = 270
    filas = {nombre: (unidad, absoluta, relativa)
             for nombre, unidad, absoluta, relativa in resumen.diferencias(base, otro)}
    assert filas["Muertes"] == ("personas simuladas", 65, None)
    assert filas["Tasa de ataque"] == ("puntos porcentuales", 20, 1)
    assert filas["Costo monetario"] == ("MXN", None, None)
    _, _, archivo = exportar.csv_comparacion(tmp_path / "reporte.csv", datos, referencia=1)
    with archivo.open(encoding="utf-8-sig") as csv_file:
        fila = next(csv.DictReader(csv_file))
    assert fila["referencia"] == otro["nombre"] and fila["diferencia_relativa"] == "-100.00%"
    html = exportar.reporte_html(datos, "Prueba", [], referencia=0)
    assert "Diferencias entre medianas" in html and "+20.00" in html and "La frontera compara medianas" in html
    ruta = tmp_path / "comparacion.pdf"
    exportar.guardar_pdf(ruta, html, {})
    pdf = QPdfDocument()
    assert pdf.load(str(ruta)) == QPdfDocument.Error.None_
    texto = " ".join(pdf.getAllText(i).text() for i in range(pdf.pageCount()))
    assert "Diferencias entre medianas" in texto and "+20.00" in texto


def test_curvas_alinean_por_dia_y_csv_deja_vacios():
    a = [{"dia": 1, "casos_activos": 10}, {"dia": 3, "casos_activos": 30}]
    b = [{"dia": 2, "casos_activos": 20}, {"dia": 3, "casos_activos": 40}]
    agregada = resumen.curva([a, b])
    assert [(p["dia"], p["mediana"]) for p in agregada] == [(3, 35)]
    _, filas = exportar.tabla_curvas({"escenarios": [
        {"nombre": "A", "curva": resumen.curva([a])}, {"nombre": "B", "curva": resumen.curva([b])}]})
    assert filas == [[1, 10, 10, 10, None, None, None], [2, None, None, None, 20, 20, 20],
                     [3, 30, 30, 30, 40, 40, 40]]


def test_comparacion_carga_versiones_solo_de_semillas_completas():
    class Cliente:
        def __init__(self):
            self.metadatos = []

        def pedir(self, servicio, metodo, ruta, params=None):
            if ruta == "/api/v1/runs":
                assert params["engine"] == "seir-ref"
                vid = params["scenario_version_id"]
                return {"corridas": [{"id": vid * 10 + s, "seed": s, "engine": "seir-ref",
                                      "engine_version": "seir-ref-0.1", "horizon_days": 150,
                                      "scenario_name": str(vid), "version_number": 1} for s in (1, 2)]}
            if servicio == "corridas":
                self.metadatos.append(int(ruta.rsplit("/", 1)[1]))
                return {}
            if servicio == "pareto":
                assert params["runs"] == "11,21"
                return {}
            return {"corridas": [{"id": r, "serie": [{"dia": 0, "casos_activos": r}]} for r in (11, 12, 21)]}

    cliente = Cliente()
    datos = servicios.cargar_comparacion(cliente, [1, 2], "fallecimientos", "seir-ref")
    assert datos["semillas"] == [1]
    assert cliente.metadatos == []
    assert all(resumen.trazable(e) for e in datos["escenarios"])


def test_vista_comparacion_oculta_grafica_sin_version_y_cambia_referencia(qt):
    _, ventanas = qt
    ventana = type("Ventana", (), {"cliente": object()})()
    vista = VistaComparacion(ventana)
    ventanas.append(vista)
    datos = datos_comparacion()
    for r in datos["escenarios"][0]["replicas"]:
        r.update(engine="seir-ref", engine_version="seir-ref-0.1")
    vista._mostrar(datos)
    assert len(vista.g_curvas.chart().series()) == 2
    assert "Falta identificar el motor" in vista.g_frontera.chart().title()
    assert "seir-ref-0.1" in vista.fuentes.text()
    assert vista.diferencias.item(0, 0).text() == "Cierre · v1"
    vista.referencia.setCurrentIndex(1)
    assert vista.diferencias.item(0, 0).text() == "Base · v1"
    assert "supuesto" in vista.costos.item(0, 4).text()


def test_mapa_municipal_usa_xml_del_servicio(qt):
    app, ventanas = qt

    class Cliente(ClienteDeEjemplos):
        def enviar(self, servicio, metodo, ruta, cuerpo=None, params=None, publico=False):
            assert (servicio, metodo, ruta) == ("zonas", "GET", "/api/v1/zones/map")
            assert params == {"disease_id": 2, "days": 7}
            return Respuesta(ejemplo("zonas", "datos_mapa"))

    ventana = type("Ventana", (), {"cliente": Cliente()})()
    vista = DialogoZonas(None, ventana, 2, "Ejemplo")
    ventanas.append(vista)
    esperar(app)
    assert vista.tabla.item(0, 0).text() == "Abasolo"
    assert "2026-10-06 a 2026-10-08" in vista.fuente.text()
    assert vista.mapa.chart().series()[0].points()[0].x() == pytest.approx(-100.40595)
    assert xmlio.leer(ejemplo("zonas", "datos_mapa"))["serie"]["municipios"][0]["region_code"] == "19001"
    assert vista.tabla_serie.rowCount() == 3 and vista.tabla_serie.item(0, 0).text() == "2026-10-06"


def test_parametros_usan_definicion_y_unidad_del_contrato(qt, monkeypatch):
    datos = xmlio.leer(ejemplo("parametros", "estado_de_par_metros_epidemiol_gicos"))
    capturados = []

    def inspeccionar(dialogo):
        listado = dialogo.findChild(QTableWidget)
        capturados.append(listado.item(0, 0).toolTip())
        assert listado.item(0, 1).text() == "contagios por caso"
        assert listado.horizontalHeaderItem(3).text() == "Incertidumbre"
        assert listado.item(0, 3).text() == "2.39 a 3.44 (IC95)"
        assert listado.item(1, 6).text() == "Con fuente"
        assert any("es simulable" in lbl.text() for lbl in dialogo.findChildren(QLabel))

    monkeypatch.setattr(QDialog, "exec", inspeccionar)
    mostrar_parametros(None, "Influenza", datos)
    assert capturados == [datos["detalle"][0]["ayuda"]]


def test_editor_descarta_respuesta_vieja_y_conserva_version_si_falla_validacion(qt, monkeypatch):
    _, ventanas = qt

    class Ventana:
        cliente = ClienteDeEjemplos()

        def es_admin(self):
            return True

    vista = escenarios.VistaEscenarios(Ventana())
    ventanas.append(vista)
    pendientes = []
    monkeypatch.setattr(escenarios, "en_hilo", lambda fn, *args, **kw: pendientes.append(kw))
    detalle = xmlio.leer(ejemplo("escenarios", "consultar_escenario"))
    detalle["version"].update(autor="Ana", revisor="Revisor")
    versiones = xmlio.leer(ejemplo("escenarios", "historial_versiones"))["versiones"]
    vista.abrir(12, 1)
    vista.abrir(12, 2)
    pendientes[1]["listo"]((detalle, versiones))
    pendientes[0]["listo"]((dict(detalle, name="Respuesta vieja"), versiones))
    assert "Respuesta vieja" not in vista.titulo.text()
    pendientes[2]["fallo"](RuntimeError())
    assert "no disponible" in vista.validacion.text()
    assert "Revisor: Revisor" in vista.ficha_version.text()
    assert vista.b_parametros.isEnabled()


def test_intervenciones_muestran_intervalo_incluyente(qt):
    _, ventanas = qt
    vista = FormIntervencion()
    ventanas.append(vista)
    vista.poner_tipos([], 10)
    vista.inicio.setValue(4)
    vista.fin.setValue(4)
    assert "1 día (" in vista.duracion.text()
    vista.hasta_el_final.setChecked(True)
    assert "7 días" in vista.duracion.text()


def test_seguir_y_cancelar_lote_limitan_la_accion_al_motor_seleccionado(qt, monkeypatch):
    _, ventanas = qt

    class Ventana:
        cliente = object()

        def accion(self, texto):
            pass

    vista = simulaciones.VistaSimulaciones(Ventana())
    ventanas.append(vista)
    x = {"scenario_version_id": 2, "scenario_name": "Escenario", "version_number": 1,
         "status": "encolado", "seed": 1}
    vista.corridas = [dict(x, id=41, engine="seir-ref"), dict(x, id=42, engine="seir-ref", seed=0),
                       dict(x, id=420, engine="abm-ref")]
    vista.seguir(42)
    assert [r["id"] for r in vista.visibles] == [42]
    assert vista.d_campos["seed"].text() == "0"
    canceladas = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    monkeypatch.setattr(simulaciones, "en_hilo", lambda fn, c, ids, **kwargs: canceladas.extend(ids))
    vista.cancelar_lote()
    assert canceladas == [41, 42]
