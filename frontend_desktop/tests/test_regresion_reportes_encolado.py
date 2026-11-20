import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QMessageBox, QProgressDialog, QPushButton
)

from frontend_desktop.app import api, exportar, resumen
from frontend_desktop.app.ui import comparacion, simulaciones
from frontend_desktop.tests.test_humo import datos_comparacion


@pytest.fixture
def abrir_vista():
    app = QApplication.instance() or QApplication([])
    vistas = []

    def abrir(tipo, ventana):
        vista = tipo(ventana)
        vistas.append(vista)
        return vista

    yield abrir
    for vista in vistas:
        vista.close()
        vista.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_reporte_completo_y_advertencia(tmp_path):
    app = QApplication.instance() or QApplication([])
    datos = datos_comparacion()

    imagenes = {
        nombre: QImage(700, 450, QImage.Format_RGB32)
        for nombre in ("frontera.png", "curvas.png")
    }
    for imagen in imagenes.values():
        imagen.fill(Qt.white)

    html = exportar.reporte_html(
        datos, "Prueba", list(imagenes)
    )

    # Estos datos ficticios no tienen bandas superpuestas.
    assert resumen.avisos_bandas(datos["escenarios"]) == []

    ruta = tmp_path / "reporte.pdf"
    exportar.guardar_pdf(ruta, html, imagenes)

    pdf = QPdfDocument()
    pdf.load(str(ruta))

    assert pdf.pageCount() == 2
    a4 = pdf.pagePointSize(0)
    assert a4.width() == pytest.approx(842, abs=1)
    assert a4.height() == pytest.approx(595, abs=1)

    primera = pdf.getAllText(0).text()
    segunda = pdf.getAllText(1).text()

    assert "Comparación de escenarios" in primera
    assert "Frontera de eficiencia" in primera
    assert "Casos activos por escenario" in primera
    assert "Indicadores por escenario" in segunda
    assert "Base" in segunda
    assert "Cierre" in segunda

    # Ahora sí simulamos bandas superpuestas.
    primero = datos["escenarios"][0]["impacto"]
    segundo = datos["escenarios"][1]["impacto"]
    segundo["p5"] = primero["p5"]
    segundo["p95"] = primero["p95"]

    html_con_aviso = exportar.reporte_html(
        datos, "Prueba", list(imagenes)
    )
    assert "Advertencia p5–p95" in html_con_aviso


def test_exportar_pdf_avisa_si_no_se_puede_escribir(tmp_path, monkeypatch, abrir_vista):
    ruta = tmp_path / "no-existe" / "reporte.pdf"
    mensajes = []

    class VentanaPrueba:
        cliente = object()

        def mostrar_error(self, error):
            mensajes.append(str(error))

        def accion(self, mensaje):
            pytest.fail(mensaje)

    vista = abrir_vista(comparacion.VistaComparacion, VentanaPrueba())
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(ruta), ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: pytest.fail(args[2]))
    monkeypatch.setattr(vista, "_imagenes", dict)
    monkeypatch.setattr(vista, "_html", lambda imagenes: "<p>Reporte de prueba</p>")
    vista.exportar_pdf()

    assert mensajes and "Elige otra ubicación" in mensajes[0]
    assert not ruta.exists()


@pytest.mark.parametrize("resultado", ["completo", "detenido", "fallido"])
def test_encolado_sin_crear_corridas(monkeypatch, resultado, abrir_vista):
    class VentanaPrueba:
        cliente = None

        def es_admin(self):
            return False

        def accion(self, mensaje):
            pass

        def mostrar_error(self, error):
            mensajes.append(str(error))

    vista = abrir_vista(simulaciones.VistaSimulaciones, VentanaPrueba())

    boton = QCheckBox("Versión de prueba")
    boton.setChecked(True)

    vista.fichas = {2: boton}
    vista.datos_fichas = {
        2: {"version_id": 2, "nombre": "Prueba"}
    }

    vista.replicas.setValue(2)
    vista._estimar()

    mensajes = []

    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args: QMessageBox.Yes
    )
    monkeypatch.setattr(
        QMessageBox, "information",
        lambda *args: mensajes.append(args[2]) or QMessageBox.Ok
    )
    monkeypatch.setattr(vista, "refrescar", lambda: None)

    def hilo_simulado(fn, *args, listo=None, fallo=None, avance=None):
        assert fn is simulaciones._lanzar_lote
        assert not vista.encolar.isEnabled()

        dialogos = vista.findChildren(QProgressDialog)
        assert len(dialogos) == 1

        dialogo = dialogos[0]
        assert dialogo.windowModality() == Qt.NonModal
        assert not dialogo.autoClose()
        assert not dialogo.autoReset()
        assert dialogo.isVisible()
        assert dialogo.value() == 0

        avance(1, "Prueba")
        if resultado == "detenido":
            dialogo.findChild(QPushButton).click()
            assert args[-1].is_set()
            assert not vista.encolar.isEnabled()
            avance(2, "Prueba")
            assert not dialogo.isVisible()
            listo((1, []))
        elif resultado == "fallido":
            fallo(api.ErrorServicio("No se pudo conectar con corridas."))
        else:
            avance(2, "Prueba")
            assert dialogo.isVisible()
            listo((2, []))
        assert not dialogo.isVisible()
        assert args[-1].is_set() == (resultado == "detenido")

    monkeypatch.setattr(
        simulaciones, "en_hilo", hilo_simulado
    )

    vista.lanzar()
    assert not vista._encolando
    assert vista.encolar.isEnabled()
    assert len(mensajes) == 1
    esperados = {"completo": "2 de 2", "detenido": "1 de 2", "fallido": "No se pudo conectar"}
    assert esperados[resultado] in mensajes[0]
    if resultado == "detenido":
        assert "Se detuvo el envío" in mensajes[0]
