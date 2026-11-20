from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QLabel, QMessageBox,
                               QTextBrowser, QVBoxLayout)

from .. import exportar, servicios
from .comun import sim
from .tareas import en_hilo


class DialogoCorrida(QDialog):
    def __init__(self, padre, ventana, corrida):
        super().__init__(padre)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Ficha de %s" % sim(corrida["id"]))
        self.resize(800, 650)
        self.v = ventana
        self.corrida = corrida
        self.resultado = None
        self.html = ""

        capa = QVBoxLayout(self)
        self.contenido = QTextBrowser()
        self.contenido.setPlainText("Consultando el resultado guardado…")
        capa.addWidget(self.contenido)
        self.estado = QLabel()
        self.estado.setTextFormat(Qt.PlainText)
        self.estado.setWordWrap(True)
        capa.addWidget(self.estado)
        botones = QDialogButtonBox(QDialogButtonBox.Close)
        botones.rejected.connect(self.reject)
        self.escenario = botones.addButton("Abrir escenario", QDialogButtonBox.ActionRole)
        self.pdf = botones.addButton("Exportar ficha PDF", QDialogButtonBox.ActionRole)
        self.equivalente = botones.addButton("Buscar corrida equivalente", QDialogButtonBox.ActionRole)
        self.repetir = botones.addButton("Encolar con la misma semilla", QDialogButtonBox.ActionRole)
        self.escenario.clicked.connect(self.abrir_escenario)
        self.pdf.clicked.connect(self.exportar_pdf)
        self.equivalente.clicked.connect(self.buscar_equivalente)
        self.repetir.clicked.connect(self.reencolar)
        for boton in (self.escenario, self.pdf, self.equivalente, self.repetir):
            boton.setEnabled(False)
        capa.addWidget(botones)
        en_hilo(servicios.resultado_corrida, self.v.cliente, corrida["id"],
                listo=self._mostrar, fallo=self._fallo_carga)

    def _mostrar(self, resultado):
        self.resultado = resultado
        self.html = exportar.reporte_corrida(resultado, self.corrida.get("engine"))
        self.contenido.setHtml(self.html)
        self.pdf.setEnabled(True)
        self.equivalente.setEnabled(bool(resultado.get("scenario_checksum")))
        datos = resultado["corrida"]
        self.escenario.setEnabled(bool(datos.get("scenario_id") and datos.get("version_number")))
        self.repetir.setEnabled(bool(self.corrida.get("engine") and datos.get("scenario_version_id")
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
            self.estado.setText("El servicio no encontró otra corrida completada con la misma huella.")
            return
        coincide = otra.get("resumen") == self.resultado["resumen"]
        self.estado.setText("%s tiene la misma huella. Los resúmenes %s."
                            % (sim(otra["id"]), "coinciden" if coincide else "son diferentes"))

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
                self.corrida["engine"], listo=self._encolada, fallo=self._fallo_reencolar)

    def _encolada(self, nueva):
        self.v.accion("repite %s como %s" % (sim(self.corrida["id"]), sim(nueva["id"])))
        self.estado.setText("%s encolada. Consulta su avance en Simulaciones." % sim(nueva["id"]))

    def _fallo_reencolar(self, exc):
        self.repetir.setEnabled(True)
        self.estado.clear()
        self.v.mostrar_error(exc)

    def exportar_pdf(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar ficha PDF", "%s.pdf" % sim(self.corrida["id"]),
                                             "PDF (*.pdf)")
        if ruta:
            try:
                exportar.guardar_pdf(ruta, self.html, {})
            except OSError:
                self.v.mostrar_error(OSError("No se pudo guardar la ficha PDF. Elige otra ubicación."))
                return
            self.v.accion("exporta la ficha de %s a %s" % (sim(self.corrida["id"]), ruta))
            QMessageBox.information(self, "Exportar", "Ficha guardada en %s." % ruta)
