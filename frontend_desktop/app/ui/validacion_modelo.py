from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget)

from .. import servicios
from .comun import celda, tabla
from .tareas import en_hilo


PARAMETROS = (
    ("R₀", "r0"), ("Incubación (días)", "incubacion_dias"),
    ("Periodo infeccioso (días)", "infeccioso_dias"), ("Hospitalización (días)", "dias_hospitalizacion"),
)


class DialogoValidacionModelo(QDialog):
    def __init__(self, padre, ventana, escenario):
        super().__init__(padre)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Validación del modelo")
        self.resize(900, 520)
        self.ventana = ventana
        self.version = escenario.get("version") or {}
        pestanas = QTabWidget()
        estado = QWidget()
        capa_estado = QVBoxLayout(estado)
        self.estado = self._nota("Consultando el estado de calibración del servidor…")
        capa_estado.addWidget(self.estado)
        self.modelos = tabla(["Versión", "Estado", "Categoría", "Motivo", "Evidencia"], estirar=(3, 4))
        capa_estado.addWidget(self.modelos)
        ver = QPushButton("Ver calibraciones y ajuste con datos observados")
        ver.clicked.connect(lambda: (ventana.ir(5), self.close()))
        capa_estado.addWidget(ver)
        pestanas.addTab(estado, "Estado de calibración")

        estudio = QWidget()
        capa_estudio = QVBoxLayout(estudio)
        fila = QHBoxLayout()
        self.parametro = QComboBox()
        for nombre, clave in PARAMETROS:
            self.parametro.addItem(nombre, clave)
        self.cambios = QLineEdit()
        self.cambios.setPlaceholderText("Porcentajes separados por comas")
        self.calcular = QPushButton("Consultar sensibilidad")
        self.calcular.clicked.connect(self.consultar)
        self.calcular.setEnabled(self.version.get("status") == "aprobado" and bool(self.version.get("id")))
        fila.addWidget(self.parametro)
        fila.addWidget(self.cambios, 1)
        fila.addWidget(self.calcular)
        capa_estudio.addLayout(fila)
        self.nota = self._nota("Estudio exploratorio de un factor a la vez. "
                               + ("Ingresa hasta nueve cambios porcentuales separados por comas."
                                  if self.calcular.isEnabled() else "El servicio requiere una versión aprobada."))
        capa_estudio.addWidget(self.nota)
        self.filas = tabla(["Valor", "Cambio (%)", "Media", "Mínimo", "Máximo", "Diferencia con base"],
                           estirar=(0,))
        capa_estudio.addWidget(self.filas)
        pestanas.addTab(estudio, "Sensibilidad exploratoria")
        capa = QVBoxLayout(self)
        capa.addWidget(pestanas)
        botones = QDialogButtonBox(QDialogButtonBox.Close)
        botones.button(QDialogButtonBox.Close).setText("Cerrar")
        botones.rejected.connect(self.reject)
        capa.addWidget(botones)
        en_hilo(servicios.estado_calibracion, ventana.cliente, escenario["disease_id"], escenario["region_id"],
                listo=self._mostrar_estado, fallo=self._fallo_estado)

    def _nota(self, texto):
        etiqueta = QLabel(texto)
        etiqueta.setTextFormat(Qt.PlainText)
        etiqueta.setWordWrap(True)
        return etiqueta

    def _mostrar_estado(self, datos):
        self.estado.setText("\n".join(datos[k] for k in ("aviso", "nota") if datos.get(k)))
        modelos = datos.get("modelos") or []
        self.modelos.setRowCount(len(modelos))
        for fila, modelo in enumerate(modelos):
            for col, campo in enumerate(("engine_version", "estado", "categoria", "motivo", "evidencia")):
                valor = modelo.get(campo)
                item = celda(valor)
                item.setToolTip(valor or "")
                self.modelos.setItem(fila, col, item)

    def _fallo_estado(self, exc):
        self.estado.setText("El servidor no devolvió el estado de calibración.")
        self.ventana.mostrar_error(exc)

    def consultar(self):
        cambios = self.cambios.text().strip()
        if not cambios:
            self.nota.setText("Ingresa los cambios porcentuales que quieres consultar.")
            return
        self.calcular.setEnabled(False)
        self.filas.setRowCount(0)
        self.nota.setText("Consultando el estudio exploratorio del servidor…")
        en_hilo(servicios.sensibilidad, self.ventana.cliente, self.version["id"], self.parametro.currentData(),
                cambios, listo=self._mostrar_sensibilidad, fallo=self._fallo_sensibilidad)

    def _mostrar_sensibilidad(self, datos):
        self.calcular.setEnabled(True)
        notas = [datos[k] for k in ("aviso", "texto_categoria", "metodo") if datos.get(k)]
        notas.append("Motor: %s · métrica: %s · valor de referencia: %s."
                     % (datos.get("engine_version"), datos.get("metrica"), datos.get("valor_base")))
        self.nota.setText("\n".join(notas))
        filas = datos.get("filas") or []
        self.filas.setRowCount(len(filas))
        for fila, resultado in enumerate(filas):
            for col, campo in enumerate(("valor", "cambio_parametro_pct", "media", "minimo", "maximo", "diferencia_vs_base")):
                self.filas.setItem(fila, col, celda(resultado.get(campo)))

    def _fallo_sensibilidad(self, exc):
        self.calcular.setEnabled(True)
        self.nota.setText("El servidor no devolvió el estudio de sensibilidad.")
        self.ventana.mostrar_error(exc)
