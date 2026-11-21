import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from frontend_desktop.app import config, exportar, servicios, xmlio
from frontend_desktop.app.ui.comparacion import VistaComparacion
from frontend_desktop.app.ui.corrida import DialogoCorrida
from frontend_desktop.app.ui.formularios import FormIntervencion
from frontend_desktop.tests.test_humo import ClienteDeEjemplos, Respuesta, datos_comparacion, esperar


@pytest.fixture
def qt():
    app = QApplication.instance() or QApplication([])
    yield app
    esperar(app)
    for widget in app.topLevelWidgets():
        if isinstance(widget, (DialogoCorrida, FormIntervencion, VistaComparacion)):
            widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class ClienteFicha(ClienteDeEjemplos):
    def __init__(self):
        super().__init__()
        self.llamadas = []

    def enviar(self, servicio, metodo, ruta, cuerpo=None, params=None, publico=False):
        self.llamadas.append((servicio, metodo, ruta))
        ejemplos = {
            ("resultados", "GET", "/api/v1/runs/42/results"): "consultar_resultado",
            ("corridas", "GET", "/api/v1/runs/42/equivalent"): "corrida_equivalente",
            ("corridas", "POST", "/api/v1/runs"): "lanzar_corrida",
            ("parametros", "GET", "/api/v1/diseases/2/parameters"): "consultar_par_metros_epidemiol_gicos",
        }
        archivo = ejemplos[servicio, metodo, ruta] + ".xml"
        if metodo == "POST":
            assert xmlio.leer(cuerpo) == {"scenario_version_id": 11, "seed": 982314, "engine": "seir-ref"}
        return Respuesta((config.CONTRATOS / servicio / "ejemplos" / archivo).read_bytes())


def test_ficha_lee_xml_y_exporta_pdf(qt, monkeypatch, tmp_path):
    abiertas = []

    class Ventana:
        cliente = ClienteFicha()

        def accion(self, texto):
            pass

        def mostrar_error(self, exc):
            pytest.fail(str(exc))

        def abrir_escenario(self, escenario, version):
            abiertas.append((escenario, version))

    cliente = Ventana.cliente
    ficha = DialogoCorrida(None, Ventana(), {"id": 42, "engine": "seir-ref"})
    esperar(qt)
    contenido = ficha.contenido.toPlainText()
    assert all(valor in contenido for valor in ("982314", "seir-ref-0.1", "r0", "1.8", "supuesto"))
    assert cliente.llamadas == [("resultados", "GET", "/api/v1/runs/42/results")]
    ficha.equivalente.click()
    esperar(qt)
    assert "SIM-0040" in ficha.estado.text()

    ruta = tmp_path / "ficha.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(ruta), ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: QMessageBox.Ok)
    ficha.pdf.click()
    pdf = QPdfDocument()
    assert pdf.load(str(ruta)) == QPdfDocument.Error.None_
    paginas = " ".join(pdf.getAllText(i).text() for i in range(pdf.pageCount()))
    assert all(valor in paginas for valor in ("Ficha de la corrida SIM-0042", "seir-ref-0.1", "r0",
                                               "Casos activos de la corrida", "Metodología"))

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.No)
    ficha.repetir.click()
    assert not any(metodo == "POST" for _, metodo, _ in cliente.llamadas)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    ficha.repetir.click()
    esperar(qt)
    assert cliente.llamadas[-1] == ("corridas", "POST", "/api/v1/runs")
    assert "encolada" in ficha.estado.text() and not ficha.repetir.isEnabled()
    ficha.escenario.click()
    assert abiertas == [(3, 2)]


def test_comparacion_muestra_corridas_de_la_curva_elegida(qt, monkeypatch):
    class Ventana:
        cliente = object()

    comparacion = VistaComparacion(Ventana())
    datos = datos_comparacion()
    for e in datos["escenarios"]:
        for r in e["replicas"]:
            r["engine"] = "seir-ref"
            r["engine_version"] = "seir-ref-0.1"
    comparacion._mostrar(datos)
    assert comparacion.replicas.currentText() == "SIM-0011 · Semilla 1"
    marcador = next(m for m in comparacion.g_curvas.chart().legend().markers() if m.label() == "Cierre · v1")
    marcador.clicked.emit()
    esperar(qt)
    comparacion.replicas.setCurrentIndex(1)
    abiertas = []

    class Dialogo:
        def __init__(self, padre, ventana, corrida):
            abiertas.append(corrida["id"])

        def open(self):
            pass

    monkeypatch.setattr("frontend_desktop.app.ui.comparacion.DialogoCorrida", Dialogo)
    comparacion.b_ficha.click()
    assert abiertas == [22]
    assert "día 0 a 4" in comparacion.fuentes.text()
    html = exportar.reporte_html(datos, "Prueba", [])
    assert "SIM-0022 (semilla 2)" in html


def test_catalogo_lee_parametros_publicos_y_xsd():
    cliente = ClienteFicha()
    datos = servicios.parametros_enfermedad(cliente, 2)
    assert datos["r0"] == {"valor": 1.3, "fuente": "Biggerstaff et al. 2014", "supuesto": False}


def test_intervencion_distingue_costo_cero_de_costo_ausente(qt):
    vista = FormIntervencion()
    vista.poner_tipos([
        {"name": "A", "code": "A", "unit_cost": 0, "cost_unit": "por_dosis", "cost_is_assumption": True},
        {"name": "B", "code": "B", "unit_cost": None},
    ], 10)
    assert "$0.00 MXN (por dosis)" in vista.costo.text()
    assert "supuesto" in vista.costo.text()
    vista.tipo.setCurrentIndex(1)
    assert vista.costo.text() == "Costo unitario del catálogo: sin dato."
