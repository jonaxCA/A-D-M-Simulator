from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)

from .. import servicios
from .comun import celda, tabla
from .formularios import texto_intervalo
from .tareas import en_hilo

COLUMNAS = ["Parámetro", "Unidad", "Catálogo", "En esta versión", "Incertidumbre", "Fuente", "Estado"]
ESTADOS = {"supuesto": "Supuesto", "con_fuente": "Con fuente", "sin_fuente": "Sin fuente", "falta": "Falta",
           "por_grupo": "Por grupo de edad"}
TIPOS = ("IC95", "RIC", "rango")


def _escala(p):
    # Las tasas se muestran y se capturan en %, y el servidor las guarda de 0 a 1.
    return 100.0 if p.get("porcentaje") else 1.0


def texto_valor(valor, p):
    if valor is None or isinstance(valor, dict):
        return None
    return "%g%s" % (valor * _escala(p), " %" if p.get("porcentaje") else "")


def ajuste_de(p, valor, fuente, supuesto, intervalo):
    # El cuerpo del PUT de un parámetro, en las unidades del servidor.
    escala = _escala(p)
    cuerpo = {"valor": valor / escala, "fuente": fuente.strip() or None, "supuesto": supuesto}
    if intervalo:
        cuerpo["intervalo"] = {"min": intervalo[0] / escala, "max": intervalo[1] / escala, "tipo": intervalo[2]}
    return cuerpo


class DialogoAjustes(QDialog):
    """Parámetros de una versión de escenario (D59): los del catálogo y lo que esta versión cambia."""

    def __init__(self, padre, ventana, version_id, enfermedad, editable):
        super().__init__(padre)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Parámetros de la versión · %s" % enfermedad)
        self.resize(1040, 640)
        self.ventana, self.version_id, self.puede = ventana, version_id, editable
        self.datos, self.filas, self.ocupado = None, [], False
        capa = QVBoxLayout(self)
        self.nota = QLabel("Consultando los parámetros de la versión…")
        self.nota.setWordWrap(True)
        self.nota.setTextFormat(Qt.PlainText)
        capa.addWidget(self.nota)
        self.tabla = tabla(COLUMNAS, estirar=(0, 5))
        self.tabla.currentCellChanged.connect(lambda fila, *_: self._elegir(fila))
        capa.addWidget(self.tabla, 1)

        self.valor = QDoubleSpinBox()
        self.valor.setDecimals(6)
        self.fuente = QLineEdit()
        self.fuente.setPlaceholderText("Fuente (cita) o marca el supuesto")
        self.supuesto = QCheckBox("Es un supuesto del equipo")
        self.con_intervalo = QCheckBox("Con intervalo de incertidumbre")
        self.i_min, self.i_max = QDoubleSpinBox(), QDoubleSpinBox()
        for caja in (self.i_min, self.i_max):
            caja.setDecimals(6)
        self.i_tipo = QComboBox()
        self.i_tipo.addItems(TIPOS)
        self.con_intervalo.toggled.connect(self._habilita_intervalo)
        self.ayuda = QLabel()
        self.ayuda.setObjectName("nota")
        self.ayuda.setWordWrap(True)
        self.ayuda.setTextFormat(Qt.PlainText)
        form = QFormLayout()
        form.addRow(self.ayuda)
        form.addRow("Valor en esta versión", self.valor)
        form.addRow("Fuente", self.fuente)
        form.addRow("", self.supuesto)
        form.addRow("", self.con_intervalo)
        fila = QHBoxLayout()
        for texto, caja in (("de", self.i_min), ("a", self.i_max), ("tipo", self.i_tipo)):
            fila.addWidget(QLabel(texto))
            fila.addWidget(caja)
        form.addRow("Intervalo", fila)
        capa.addLayout(form)
        self.edicion = [self.valor, self.fuente, self.supuesto, self.con_intervalo]

        botones = QHBoxLayout()
        self.aplicar = QPushButton("Aplicar ajuste")
        self.aplicar.setObjectName("primario")
        self.quitar = QPushButton("Volver al catálogo")
        self.aplicar.clicked.connect(self._aplicar)
        self.quitar.clicked.connect(self._quitar)
        botones.addStretch(1)
        botones.addWidget(self.quitar)
        botones.addWidget(self.aplicar)
        capa.addLayout(botones)
        cerrar = QDialogButtonBox(QDialogButtonBox.Close)
        cerrar.button(QDialogButtonBox.Close).setText("Cerrar")
        cerrar.rejected.connect(self.reject)
        capa.addWidget(cerrar)
        self._habilita(False)
        en_hilo(servicios.ajustes_version, ventana.cliente, version_id, listo=self._mostrar, fallo=self._fallo)

    def _habilita_intervalo(self, activo):
        for caja in (self.i_min, self.i_max, self.i_tipo):
            caja.setEnabled(activo and self.valor.isEnabled())

    def _habilita(self, activo):
        for caja in self.edicion:
            caja.setEnabled(activo)
        self.aplicar.setEnabled(activo)
        self._habilita_intervalo(self.con_intervalo.isChecked())
        self.quitar.setEnabled(False)

    def _editable(self):
        return bool(self.puede and self.datos and self.datos.get("editable"))

    def _mostrar(self, datos):
        self.ocupado = False
        self.datos = datos
        detalle = (datos.get("estado") or {}).get("detalle") or []
        catalogo, ajustes = datos.get("catalogo") or {}, datos.get("ajustes") or {}
        self.filas = detalle
        elegida = self.tabla.currentRow()
        self.tabla.setRowCount(len(detalle))
        for fila, p in enumerate(detalle):
            ajustado = p["clave"] in ajustes
            base = catalogo.get(p["clave"])
            valores = (p.get("etiqueta") or p["clave"], p.get("unidad"),
                       texto_valor(base.get("valor") if isinstance(base, dict) else None, p),
                       texto_valor(p.get("valor"), p), texto_intervalo(p.get("intervalo")),
                       p.get("fuente") or ("Supuesto" if p.get("supuesto") else None),
                       "Ajustado" if ajustado else ESTADOS.get(p.get("estado"), p.get("estado")))
            for col, dato in enumerate(valores):
                self.tabla.setItem(fila, col, celda(dato, "aprobado" if ajustado and col == 6 else None))
            self.tabla.item(fila, 0).setToolTip(p.get("ayuda") or "")
        if self._editable():
            self.nota.setText("Los ajustes son solo de esta versión y el catálogo no cambia. Al enviarla a revisión "
                              "se congela el catálogo con tus ajustes, y quien revisa los ve. Cada ajuste lleva "
                              "fuente o la marca de supuesto.")
        else:
            self.nota.setText("Solo se pueden ajustar los parámetros del borrador vigente de tu escenario. Esta "
                              "versión (%s) ya no es editable o no es tuya: ves los parámetros con que se simula."
                              % (datos.get("status") or "sin dato"))
        self._habilita(False)
        if 0 <= elegida < len(detalle):
            self.tabla.selectRow(elegida)
            self._elegir(elegida)
        else:
            self.ayuda.clear()

    def _parametro(self, fila):
        if not (0 <= fila < len(self.filas)):
            return None
        p = self.filas[fila]
        if p.get("min") is None or p.get("max") is None or p.get("estado") == "por_grupo":
            return None
        return p

    def _elegir(self, fila):
        p = self._parametro(fila)
        self._habilita(bool(p) and self._editable() and not self.ocupado)
        if not p:
            self.ayuda.setText("Este parámetro viene por grupo de edad y no se ajusta aquí." if 0 <= fila < len(self.filas)
                               else "")
            return
        escala = _escala(p)
        for caja in (self.valor, self.i_min, self.i_max):
            caja.setRange(p["min"], p["max"])
            caja.setSingleStep(float(p.get("paso") or 0.01))
        self.ayuda.setText("%s Rango del motor: %g a %g %s." % (p.get("ayuda") or "", p["min"], p["max"],
                                                                p.get("unidad") or ""))
        valor = p.get("valor")
        self.valor.setValue(p["min"] if valor is None else valor * escala)
        self.fuente.setText(p.get("fuente") or "")
        self.supuesto.setChecked(bool(p.get("supuesto")))
        intervalo = p.get("intervalo")
        self.con_intervalo.setChecked(bool(intervalo))
        if intervalo:
            self.i_min.setValue(intervalo["min"] * escala)
            self.i_max.setValue(intervalo["max"] * escala)
            self.i_tipo.setCurrentText(intervalo.get("tipo") or "rango")
        self._habilita_intervalo(bool(intervalo))
        self.quitar.setEnabled(self._editable() and p["clave"] in (self.datos.get("ajustes") or {}))

    def _enviar(self, cambios):
        self.ocupado = True
        self._habilita(False)
        self.nota.setText("Guardando el ajuste…")
        en_hilo(servicios.ajustar_version, self.ventana.cliente, self.version_id, cambios,
                listo=self._mostrar, fallo=self._fallo)

    def _aplicar(self):
        p = self._parametro(self.tabla.currentRow())
        if not p:
            return
        intervalo = (self.i_min.value(), self.i_max.value(), self.i_tipo.currentText()) \
            if self.con_intervalo.isChecked() else None
        self._enviar({p["clave"]: ajuste_de(p, self.valor.value(), self.fuente.text(),
                                            self.supuesto.isChecked(), intervalo)})

    def _quitar(self):
        p = self._parametro(self.tabla.currentRow())
        if p:
            self._enviar({p["clave"]: None})

    def _fallo(self, exc):
        self.ocupado = False
        if self.datos:
            self._mostrar(self.datos)
        else:
            self.nota.setText("El servidor no devolvió los parámetros de la versión.")
        self.ventana.mostrar_error(exc)
