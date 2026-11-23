from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QSpinBox,
                               QVBoxLayout, QWidget)

from .comun import celda, fecha, tabla

POLITICAS = (("excluir", "Excluir a quienes no tienen edad"), ("prorratear", "Repartir según la estructura"))
POBLACION_MAX = 20_000_000


def texto_intervalo(intervalo):
    # El intervalo con que el parámetro se publica (D58); el motor solo usa el valor.
    if not isinstance(intervalo, dict) or intervalo.get("min") is None or intervalo.get("max") is None:
        return None
    return "%s a %s (%s)" % (intervalo["min"], intervalo["max"], intervalo.get("tipo") or "intervalo")


def mostrar_parametros(padre, enfermedad, datos, versiones=None):
    dialogo = QDialog(padre)
    dialogo.setWindowTitle("Parámetros de %s" % enfermedad)
    dialogo.resize(1000, 520)
    capa = QVBoxLayout(dialogo)
    if datos.get("simulable") is True:
        estado = "El catálogo indica que la enfermedad es simulable."
    elif datos.get("simulable") is False:
        estado = "El catálogo indica que la enfermedad todavía no es simulable."
    else:
        estado = "El catálogo no informó si la enfermedad es simulable."
    vigente = " (versión %s)" % versiones[0]["version"] if versiones else ""
    nota = QLabel(estado + " Estos valores son del catálogo vigente%s. Cada versión de un escenario congela los suyos al enviarse; "
                  "los valores de una corrida están en su ficha." % vigente)
    nota.setTextFormat(Qt.PlainText)
    nota.setWordWrap(True)
    capa.addWidget(nota)
    detalle = (datos.get("detalle") or []) + (datos.get("informativos") or [])
    if detalle:
        listado = tabla(["Parámetro", "Unidad", "Valor", "Incertidumbre", "Rango del motor", "Fuente", "Estado"], estirar=(0, 5))
        listado.setRowCount(len(detalle))
        estados = {"supuesto": "Supuesto", "con_fuente": "Con fuente", "sin_fuente": "Sin fuente",
                   "falta": "Falta", "por_grupo": "Por grupo de edad"}
        for fila, p in enumerate(detalle):
            rango = "%s a %s" % (p["min"], p["max"]) if p.get("min") is not None and p.get("max") is not None else None
            estado = estados.get(p.get("estado"), "Supuesto" if p.get("supuesto") else "Informativo")
            valor = p.get("valor_form") or p.get("valor")
            if isinstance(valor, dict):
                valor = "; ".join("%s: %s" % item for item in valor.items())
            valores = (p.get("etiqueta") or p.get("clave"), p.get("unidad"), valor, texto_intervalo(p.get("intervalo")),
                       rango, p.get("fuente") or None, estado)
            for col, dato in enumerate(valores):
                listado.setItem(fila, col, celda(dato))
            listado.item(fila, 0).setToolTip(p.get("ayuda") or "")
        capa.addWidget(listado)
    else:
        capa.addWidget(QLabel("El catálogo no devolvió parámetros para esta enfermedad."))
    if versiones:
        capa.addWidget(QLabel("Versiones de los parámetros de la enfermedad (cada cambio guarda la versión completa):"))
        historial = tabla(["Versión", "Fecha", "Motivo"], estirar=(2,))
        historial.setMaximumHeight(130)
        historial.setRowCount(len(versiones))
        for fila, ver in enumerate(versiones):
            for col, dato in enumerate((ver.get("version"), fecha(ver.get("created_at")), ver.get("reason"))):
                historial.setItem(fila, col, celda(dato))
        capa.addWidget(historial)
    botones = QDialogButtonBox(QDialogButtonBox.Close)
    botones.button(QDialogButtonBox.Close).setText("Cerrar")
    botones.rejected.connect(dialogo.reject)
    capa.addWidget(botones)
    dialogo.exec()


def _entero(minimo, maximo, valor):
    caja = QSpinBox()
    caja.setRange(minimo, maximo)
    caja.setValue(valor)
    caja.setGroupSeparatorShown(True)
    return caja


def _fraccion(valor=1.0, minimo=0.0, maximo=1.0):
    caja = QDoubleSpinBox()
    caja.setDecimals(3)
    caja.setSingleStep(0.05)
    caja.setRange(minimo, maximo)
    caja.setValue(valor)
    return caja


def _botones(dialogo, capa):
    botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    botones.accepted.connect(dialogo.accept)
    botones.rejected.connect(dialogo.reject)
    capa.addWidget(botones)


class _CamposVersion:
    def _campos_version(self, forma, version):
        self.poblacion = _entero(1000, POBLACION_MAX, version.get("population_size") or 100000)
        self.infectados = _entero(1, POBLACION_MAX, version.get("initial_infected") or 10)
        self.horizonte = _entero(1, 1095, version.get("horizon_days") or 120)
        self.estratificar = QCheckBox("Repartir la población por edad con el censo de la región")
        self.estratificar.setChecked(bool(version.get("por_edad")))
        self.politica = QComboBox()
        for clave, texto in POLITICAS:
            self.politica.addItem(texto, clave)
        self.notas = QPlainTextEdit(version.get("notes") or "")
        self.notas.setFixedHeight(70)
        forma.addRow("Población", self.poblacion)
        forma.addRow("Infectados iniciales", self.infectados)
        forma.addRow("Horizonte (días)", self.horizonte)
        forma.addRow("", self.estratificar)
        forma.addRow("Edad no especificada", self.politica)
        forma.addRow("Notas", self.notas)

    def _datos_version(self):
        return {"population_size": self.poblacion.value(), "horizon_days": self.horizonte.value(),
                "initial_infected": self.infectados.value(), "stratify": self.estratificar.isChecked(),
                "age_unknown_policy": self.politica.currentData() if self.estratificar.isChecked() else None,
                "notes": self.notas.toPlainText().strip() or None}


class DialogoEscenario(QDialog, _CamposVersion):
    def __init__(self, padre, enfermedades, regiones):
        super().__init__(padre)
        self.setWindowTitle("Nuevo escenario")
        self.setMinimumWidth(520)
        self.nombre = QLineEdit()
        self.nombre.setMaxLength(160)
        self.descripcion = QLineEdit()
        self.enfermedad = QComboBox()
        for e in enfermedades:
            if (e.get("parametros") or {}).get("simulable") is not False:
                self.enfermedad.addItem(e["nombre"], e["id"])
        self.region = QComboBox()
        for r in sorted(regiones, key=lambda r: r["nombre"]):
            self.region.addItem("%s (%s hab.)" % (r["nombre"], "{:,}".format(r.get("poblacion") or 0)), r)
        forma = QFormLayout()
        forma.addRow("Nombre", self.nombre)
        forma.addRow("Descripción", self.descripcion)
        forma.addRow("Enfermedad", self.enfermedad)
        forma.addRow("Municipio", self.region)
        self._campos_version(forma, {})
        self.region.currentIndexChanged.connect(self._poblacion_de_region)
        self._poblacion_de_region()
        self.error = QLabel()
        self.error.setStyleSheet("color: #B91C1C;")
        capa = QVBoxLayout(self)
        capa.addLayout(forma)
        capa.addWidget(self.error)
        _botones(self, capa)

    def _poblacion_de_region(self):
        region = self.region.currentData()
        if region and region.get("poblacion"):
            self.poblacion.setValue(min(region["poblacion"], POBLACION_MAX))

    def accept(self):
        if not self.nombre.text().strip() or self.enfermedad.currentData() is None:
            self.error.setText("El nombre y la enfermedad son obligatorios.")
            return
        super().accept()

    def datos(self):
        datos = {"name": self.nombre.text().strip(), "description": self.descripcion.text().strip() or None,
                 "disease_id": self.enfermedad.currentData(), "region_id": self.region.currentData()["id"]}
        datos.update(self._datos_version())
        return datos


class DialogoVersion(QDialog, _CamposVersion):
    def __init__(self, padre, version):
        super().__init__(padre)
        self.setWindowTitle("Nueva versión")
        self.setMinimumWidth(480)
        forma = QFormLayout()
        aviso = QLabel("La versión nueva copia las intervenciones de la vigente y empieza en borrador.")
        aviso.setWordWrap(True)
        aviso.setObjectName("nota")
        self._campos_version(forma, dict(version, notes=""))
        self.error = QLabel()
        self.error.setStyleSheet("color: #B91C1C;")
        capa = QVBoxLayout(self)
        capa.addWidget(aviso)
        capa.addLayout(forma)
        capa.addWidget(self.error)
        _botones(self, capa)

    def accept(self):
        if not self.notas.toPlainText().strip():
            self.error.setText("Escribe en las notas qué cambia en esta versión.")
            return
        super().accept()

    def datos(self):
        return self._datos_version()


def _campo_parametro(esquema):
    tipo = esquema.get("type")
    if esquema.get("enum"):
        caja = QComboBox()
        caja.addItems(esquema["enum"])
        return caja, lambda: caja.currentText()
    if tipo == "integer":
        caja = _entero(int(esquema.get("minimum", 0)), int(esquema.get("maximum", 10_000_000)),
                       int(esquema.get("default", esquema.get("minimum", 0))))
        return caja, caja.value
    if tipo == "number":
        caja = _fraccion(float(esquema.get("default", esquema.get("minimum", 0))),
                         float(esquema.get("minimum", 0)), float(esquema.get("maximum", 1_000_000)))
        return caja, caja.value
    caja = QLineEdit()
    caja.setPlaceholderText("valores separados por comas" if tipo == "array" else "")
    return caja, lambda: caja.text().strip()


class FormIntervencion(QWidget):
    def __init__(self):
        super().__init__()
        self.tipos = []
        self.lectores = {}
        self.tipo = QComboBox()
        self.tipo.setMinimumWidth(210)
        self.tipo.currentIndexChanged.connect(self._parametros)
        self.descripcion = QLabel()
        self.descripcion.setWordWrap(True)
        self.descripcion.setObjectName("nota")
        self.costo = QLabel()
        self.costo.setTextFormat(Qt.PlainText)
        self.costo.setWordWrap(True)
        self.costo.setObjectName("nota")
        self.inicio = _entero(0, 1095, 0)
        self.fin = _entero(0, 1095, 30)
        self.hasta_el_final = QCheckBox("Hasta el final")
        self.hasta_el_final.toggled.connect(lambda si: self.fin.setEnabled(not si))
        self.duracion = QLabel()
        self.duracion.setWordWrap(True)
        self.duracion.setObjectName("nota")
        self.inicio.valueChanged.connect(self._duracion)
        self.fin.valueChanged.connect(self._duracion)
        self.hasta_el_final.toggled.connect(self._duracion)
        self.cobertura = _fraccion()
        self.cumplimiento = _fraccion()
        dias = QHBoxLayout()
        dias.addWidget(self.inicio)
        dias.addWidget(QLabel("a"))
        dias.addWidget(self.fin)
        dias.addWidget(self.hasta_el_final)
        dias.addStretch(1)
        self.forma = QFormLayout()
        self.forma.setRowWrapPolicy(QFormLayout.WrapAllRows)
        self.forma.addRow("Tipo de intervención", self.tipo)
        self.forma.addRow(self.descripcion)
        self.forma.addRow(self.costo)
        self.forma.addRow("Días", dias)
        self.forma.addRow(self.duracion)
        self.forma.addRow("Cobertura (0–1)", self.cobertura)
        self.forma.addRow("Cumplimiento (0–1)", self.cumplimiento)
        self.filas_fijas = self.forma.rowCount()
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.addLayout(self.forma)
        self._duracion()

    def poner_tipos(self, tipos, horizonte):
        self.tipos = tipos
        self.inicio.setMaximum(horizonte)
        self.fin.setMaximum(horizonte)
        self.tipo.blockSignals(True)
        self.tipo.clear()
        for t in tipos:
            self.tipo.addItem(t["name"], t["code"])
        self.tipo.blockSignals(False)
        self._parametros()
        self._duracion()

    def _duracion(self):
        fin = self.inicio.maximum() if self.hasta_el_final.isChecked() else self.fin.value()
        dias = fin - self.inicio.value() + 1
        unidad = "día" if dias == 1 else "días"
        texto = ("Intervalo definido: %d %s (inicio y fin incluidos)." % (dias, unidad) if dias > 0
                 else "El día final debe ser igual o posterior al inicial.")
        self.duracion.setText(texto)

    def _parametros(self):
        while self.forma.rowCount() > self.filas_fijas:
            self.forma.removeRow(self.filas_fijas)
        self.lectores = {}
        if not self.tipos:
            self.descripcion.clear()
            self.costo.clear()
            return
        tipo = self.tipos[self.tipo.currentIndex()]
        self.descripcion.setText(tipo.get("description") or "")
        costo = tipo.get("unit_cost")
        if costo is None:
            self.costo.setText("Costo unitario del catálogo: sin dato.")
        else:
            unidad = (tipo.get("cost_unit") or "unidad sin dato").replace("_", " ")
            fuente = tipo.get("cost_source") or "sin fuente"
            supuesto = " · supuesto" if tipo.get("cost_is_assumption") else ""
            self.costo.setText("Costo unitario del catálogo: ${:,.2f} MXN ({}) · {}{}"
                               .format(costo, unidad, fuente, supuesto))
        esquema = tipo.get("param_schema") or {}
        requeridos = set(esquema.get("required") or [])
        for nombre, propiedad in (esquema.get("properties") or {}).items():
            campo, leer = _campo_parametro(propiedad)
            campo.setToolTip(propiedad.get("description") or "")
            if nombre in requeridos or "default" in propiedad:
                self.forma.addRow(nombre, campo)
                self.lectores[nombre] = leer
                continue
            usar = QCheckBox(nombre)
            campo.setEnabled(False)
            usar.toggled.connect(campo.setEnabled)
            self.forma.addRow(usar, campo)
            self.lectores[nombre] = lambda leer=leer, usar=usar: leer() if usar.isChecked() else None

    def datos(self):
        if self.hasta_el_final.isChecked() is False and self.fin.value() < self.inicio.value():
            raise ValueError("El día final no puede ser antes del inicial.")
        params = {}
        for nombre, leer in self.lectores.items():
            valor = leer()
            if valor not in (None, ""):
                params[nombre] = valor
        return {"code": self.tipo.currentData(), "start_day": self.inicio.value(),
                "end_day": None if self.hasta_el_final.isChecked() else self.fin.value(),
                "coverage": self.cobertura.value(), "compliance": self.cumplimiento.value(), "params": params}
