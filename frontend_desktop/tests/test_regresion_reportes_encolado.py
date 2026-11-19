import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QMessageBox, QProgressDialog
)

from frontend_desktop.app import exportar, resumen
from frontend_desktop.app.ui import simulaciones
from frontend_desktop.tests.test_humo import datos_comparacion


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

    primera = pdf.getAllText(0).text()
    segunda = pdf.getAllText(1).text()

    assert "Comparación de escenarios" in primera
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


def test_encolado_sin_crear_corridas(monkeypatch):
    app = QApplication.instance() or QApplication([])

    class VentanaPrueba:
        cliente = None

        def es_admin(self):
            return False

        def accion(self, mensaje):
            pass

        def mostrar_error(self, error):
            raise error

    vista = simulaciones.VistaSimulaciones(VentanaPrueba())

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

        avance(1, "Prueba")
        avance(2, "Prueba")
        listo((2, []))

    monkeypatch.setattr(
        simulaciones, "en_hilo", hilo_simulado
    )

    try:
        vista.lanzar()
        assert not vista._encolando
        assert vista.encolar.isEnabled()
        assert len(mensajes) == 1
        assert "2 de 2" in mensajes[0]
    finally:
        vista.close()
