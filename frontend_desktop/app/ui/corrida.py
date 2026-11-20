from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QLabel, QMessageBox,
                               QTextBrowser, QVBoxLayout)

from .. import api, exportar, servicios
from . import graficas
from .comun import sim
from .tareas import en_hilo


def _cargar_ficha(c, corrida_id, motor):
    resultado = servicios.resultado_corrida(c, corrida_id)
    if not motor:
        try:
            motor = servicios.corrida(c, corrida_id).get("engine")
        except api.SesionCerrada:
            raise
        except api.ErrorServicio:
            pass
    return resultado, motor


class DialogoCorrida(QDialog):
    def __init__(self, padre, ventana, corrida):
        super().__init__(padre)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Ficha de %s" % sim(corrida["id"]))
        self.resize(800, 650)
        self.v = ventana
        self.corrida = corrida
        self.resultado = None
        self.nueva_id = None
        self.equivalente_id = None

        capa = QVBoxLayout(self)
        self.contenido = QTextBrowser()
        self.contenido.setPlainText("Consultando el resultado guardado…")
        capa.addWidget(self.contenido)
        self.fuente_serie = QLabel()
        self.fuente_serie.setTextFormat(Qt.PlainText)
        self.fuente_serie.setWordWrap(True)
        capa.addWidget(self.fuente_serie)
        self.g_serie = graficas.vista()
        self.g_serie.setMinimumHeight(220)
        self.g_serie.setMaximumHeight(260)
        self.g_serie.hide()
        capa.addWidget(self.g_serie)
        self.estado = QLabel()
        self.estado.setTextFormat(Qt.PlainText)
        self.estado.setWordWrap(True)
        capa.addWidget(self.estado)
        botones = QDialogButtonBox(QDialogButtonBox.Close)
        botones.button(QDialogButtonBox.Close).setText("Cerrar")
        botones.rejected.connect(self.reject)
        self.escenario = botones.addButton("Abrir escenario", QDialogButtonBox.ActionRole)
        self.pdf = botones.addButton("Exportar ficha PDF", QDialogButtonBox.ActionRole)
        self.equivalente = botones.addButton("Buscar corrida equivalente", QDialogButtonBox.ActionRole)
        self.repetir = botones.addButton("Encolar con la misma semilla", QDialogButtonBox.ActionRole)
        self.ir_equivalente = botones.addButton("Abrir resultado equivalente", QDialogButtonBox.ActionRole)
        self.seguir = botones.addButton("Ver nueva corrida", QDialogButtonBox.ActionRole)
        self.ir_equivalente.hide()
        self.seguir.hide()
        self.ir_equivalente.clicked.connect(self.abrir_equivalente)
        self.seguir.clicked.connect(self.seguir_corrida)
        self.escenario.clicked.connect(self.abrir_escenario)
        self.pdf.clicked.connect(self.exportar_pdf)
        self.equivalente.clicked.connect(self.buscar_equivalente)
        self.repetir.clicked.connect(self.reencolar)
        for boton in (self.escenario, self.pdf, self.equivalente, self.repetir):
            boton.setEnabled(False)
        capa.addWidget(botones)
        en_hilo(_cargar_ficha, self.v.cliente, corrida["id"], corrida.get("engine"),
                listo=self._mostrar, fallo=self._fallo_carga)

    def _mostrar(self, datos):
        resultado, motor = datos
        self.resultado = resultado
        self.motor = motor
        version = resultado.get("engine_version")
        self.contenido.setHtml(exportar.reporte_corrida(resultado, motor))
        serie = resultado.get("serie") or []
        if motor and version and serie:
            self.fuente_serie.setText("Fuente: resultados · día %s a %s · %s (%s) · personas simuladas."
                                     % (serie[0]["dia"], serie[-1]["dia"], motor, version))
            self.g_serie.show()
            graficas.serie_corrida(self.g_serie, serie)
        else:
            self.fuente_serie.setText("La gráfica requiere motor, versión y serie diaria del servicio.")
        self.pdf.setEnabled(True)
        self.equivalente.setEnabled(bool(resultado.get("scenario_checksum")))
        datos = resultado["corrida"]
        self.escenario.setEnabled(bool(datos.get("scenario_id") and datos.get("version_number")))
        self.repetir.setEnabled(bool(motor and datos.get("scenario_version_id")
                                     and datos.get("seed") is not None))

    def _fallo_carga(self, exc):
        self.contenido.setPlainText("No se pudo consultar la ficha de esta corrida.")
        self.v.mostrar_error(exc)

    def abrir_escenario(self):
        datos = self.resultado["corrida"]
        self.v.abrir_escenario(datos["scenario_id"], datos["version_number"])
        self.accept()

    def buscar_equivalente(self):
        self.equivalente.setEnabled(False)
        self.estado.setText("Buscando una corrida con la misma versión, semilla y huella…")
        en_hilo(servicios.corrida_equivalente, self.v.cliente, self.corrida["id"],
                listo=self._mostrar_equivalente, fallo=self._fallo_equivalente)

    def _mostrar_equivalente(self, datos):
        self.equivalente.setEnabled(True)
        otra = datos.get("equivalente")
        if not otra:
            self.equivalente_id = None
            self.ir_equivalente.hide()
            self.estado.setText("El servicio no encontró otra corrida completada con la misma huella.")
            return
        coincide = otra.get("resumen") == self.resultado["resumen"]
        self.equivalente_id = otra["id"]
        self.ir_equivalente.show()
        self.estado.setText("%s tiene la misma huella. Los resúmenes %s. Comprueba la versión del motor en ambas fichas."
                            % (sim(otra["id"]), "coinciden" if coincide else "son diferentes"))

    def abrir_equivalente(self):
        if self.equivalente_id is not None:
            DialogoCorrida(self.parentWidget(), self.v, {"id": self.equivalente_id}).open()
            self.accept()

    def _fallo_equivalente(self, exc):
        self.equivalente.setEnabled(True)
        self.estado.clear()
        self.v.mostrar_error(exc)

    def reencolar(self):
        datos = self.resultado["corrida"]
        pregunta = ("¿Encolar una corrida con la misma versión de escenario, semilla y motor? "
                    "El servidor usará el despliegue y los parámetros disponibles hoy. "
                    "Después puedes consultar si el resultado conserva la huella original.")
        if QMessageBox.question(self, "Repetir corrida", pregunta) != QMessageBox.Yes:
            return
        self.repetir.setEnabled(False)
        self.estado.setText("Encolando la nueva corrida…")
        en_hilo(servicios.lanzar_corrida, self.v.cliente, datos["scenario_version_id"], datos["seed"],
                self.motor, listo=self._encolada, fallo=self._fallo_reencolar)

    def _encolada(self, nueva):
        self.v.accion("repite %s como %s" % (sim(self.corrida["id"]), sim(nueva["id"])))
        self.nueva_id = nueva["id"]
        self.seguir.show()
        self.estado.setText("%s encolada. Consulta su avance en Simulaciones." % sim(nueva["id"]))

    def _fallo_reencolar(self, exc):
        self.repetir.setEnabled(True)
        self.estado.clear()
        self.v.mostrar_error(exc)

    def seguir_corrida(self):
        if self.nueva_id is not None:
            self.v.seguir_corrida(self.nueva_id)
            self.accept()

    def exportar_pdf(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar ficha PDF", "%s.pdf" % sim(self.corrida["id"]),
                                             "PDF (*.pdf)")
        if ruta:
            imagenes = {"serie_corrida.png": self.g_serie.grab().toImage()} if not self.g_serie.isHidden() else {}
            try:
                html = exportar.reporte_corrida(self.resultado, self.motor, bool(imagenes))
                exportar.guardar_pdf(ruta, html, imagenes)
            except OSError:
                self.v.mostrar_error(OSError("No se pudo guardar la ficha PDF. Elige otra ubicación."))
                return
            self.v.accion("exporta la ficha de %s a %s" % (sim(self.corrida["id"]), ruta))
            QMessageBox.information(self, "Exportar", "Ficha guardada en %s." % ruta)
