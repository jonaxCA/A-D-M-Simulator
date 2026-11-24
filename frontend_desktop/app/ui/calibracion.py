from html import escape

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QScrollArea, QSpinBox, QSplitter, QVBoxLayout, QWidget)

from .. import api, config, servicios
from . import graficas
from .comun import celda, encabezado, estado, fecha, num, pct, tabla, tarjeta
from .tareas import en_hilo

COLUMNAS = ("N.º", "Conjunto", "Estado", "Avance", "Solicitó", "Creada")
EN_CURSO = ("encolado", "ejecutando")
COBERTURA_MINIMA = 0.8


def _html(texto):
    return escape(str(texto)) if texto not in (None, "") else "—"


class VistaCalibracion(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.c = ventana.cliente
        self.lista = []
        self.actual = None
        self.ajuste = None
        self._solicitud = 0
        self._ocupado = False
        self.reloj = QTimer(self)
        self.reloj.timeout.connect(self.cargar)

        actualizar = QPushButton("Actualizar")
        actualizar.clicked.connect(self.cargar)
        cabeza, _ = encabezado("Trabajo", "Calibración y validación con datos observados", (actualizar,))

        divisor = QSplitter()
        divisor.addWidget(self._lista())
        divisor.addWidget(self._panel())
        divisor.setStretchFactor(0, 1)
        divisor.setStretchFactor(1, 1)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(cabeza)
        capa.addWidget(divisor, 1)
        self._habilitar()

    def _lista(self):
        caja = QWidget()
        caja.setObjectName("contenido")
        capa = QVBoxLayout(caja)
        capa.setContentsMargins(16, 16, 8, 16)

        marco, interior = tarjeta("Calibraciones")
        self.nota = QLabel("")
        self.nota.setObjectName("nota")
        self.nota.setWordWrap(True)
        self.tabla = tabla(COLUMNAS, estirar=(1,))
        self.tabla.itemSelectionChanged.connect(self._elegir)
        interior.addWidget(self.nota)
        interior.addWidget(self.tabla, 1)
        capa.addWidget(marco, 3)

        marco_nueva, nueva = tarjeta("Lanzar una calibración (seir-ref, ABC por rechazo)")
        self.conjunto = QComboBox()
        self.muestras = QSpinBox()
        self.muestras.setRange(100, 10000)
        self.muestras.setValue(5000)
        self.semillas = QSpinBox()
        self.semillas.setRange(1, 5)
        self.semillas.setValue(3)
        self.cuantil = QDoubleSpinBox()
        self.cuantil.setRange(0.001, 0.2)
        self.cuantil.setDecimals(3)
        self.cuantil.setSingleStep(0.005)
        self.cuantil.setValue(0.01)
        self.semilla_muestreo = QSpinBox()
        self.semilla_muestreo.setRange(1, 1000000)
        self.semilla_muestreo.setValue(1)
        forma = QFormLayout()
        forma.addRow("Conjunto observado", self.conjunto)
        forma.addRow("Muestras", self.muestras)
        forma.addRow("Semillas por muestra", self.semillas)
        forma.addRow("Cuantil que se acepta", self.cuantil)
        forma.addRow("Semilla del muestreo", self.semilla_muestreo)
        self.b_lanzar = QPushButton("Lanzar")
        self.b_lanzar.setObjectName("primario")
        self.b_lanzar.clicked.connect(self.lanzar)
        self.b_cancelar = QPushButton("Cancelar la seleccionada")
        self.b_cancelar.clicked.connect(self.cancelar)
        botones = QHBoxLayout()
        botones.addWidget(self.b_lanzar)
        botones.addWidget(self.b_cancelar)
        botones.addStretch(1)
        self.mensaje = QLabel("")
        self.mensaje.setWordWrap(True)
        nueva.addLayout(forma)
        nueva.addLayout(botones)
        nueva.addWidget(self.mensaje)
        capa.addWidget(marco_nueva, 2)
        return caja

    def _panel(self):
        marco, interior = tarjeta("Ajuste contra lo observado")
        self.resumen = QLabel("Elige una calibración para ver sus estimados, sus métricas y el ajuste.")
        self.resumen.setWordWrap(True)
        self.estimados = tabla(("Parámetro", "Mediana", "p5", "p95", "Rango admitido"), estirar=(0,))
        self.estimados.setMaximumHeight(130)
        self.metricas = tabla(("Ventana", "Semanas", "RMSE", "R²", "Cobertura p5–p95"), estirar=(0,))
        self.metricas.setMaximumHeight(110)
        self.grafica = graficas.vista()
        graficas.sin_datos(self.grafica, "Sin ajuste que mostrar")
        self.pie = QLabel("")
        self.pie.setObjectName("nota")
        self.pie.setWordWrap(True)
        self.b_escenario = QPushButton("Crear escenario calibrado (borrador)")
        self.b_escenario.clicked.connect(self.crear_escenario)

        evaluar, ev = tarjeta("Evaluar un juego de parámetros")
        self.r0 = self._decimal(1, 5, 2.5, 2)
        self.rho = self._decimal(0.01, 1, 0.3, 3)
        self.phi = self._decimal(0, 1, 0.4, 3)
        forma = QFormLayout()
        forma.addRow("R₀", self.r0)
        forma.addRow("ρ (proporción de casos notificados)", self.rho)
        forma.addRow("φ (reducción por las medidas)", self.phi)
        self.b_evaluar = QPushButton("Evaluar contra el conjunto elegido")
        self.b_evaluar.clicked.connect(self.evaluar)
        ev.addLayout(forma)
        ev.addWidget(self.b_evaluar)

        for parte in (self.resumen, self.estimados, self.metricas, self.grafica, self.pie, self.b_escenario, evaluar):
            interior.addWidget(parte)
        interior.addStretch(1)
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setObjectName("contenido")
        caja = QWidget()
        caja.setObjectName("contenido")
        capa = QVBoxLayout(caja)
        capa.setContentsMargins(8, 16, 16, 16)
        capa.addWidget(marco)
        desplazable.setWidget(caja)
        return desplazable

    def _decimal(self, minimo, maximo, valor, decimales):
        campo = QDoubleSpinBox()
        campo.setRange(minimo, maximo)
        campo.setDecimals(decimales)
        campo.setValue(valor)
        return campo

    def al_mostrar(self):
        if not self.conjunto.count():
            en_hilo(servicios.conjuntos, self.c, listo=self._poner_conjuntos, fallo=self.v.mostrar_error)
        self.cargar()

    def hideEvent(self, evento):
        self.reloj.stop()
        super().hideEvent(evento)

    def _poner_conjuntos(self, conjuntos):
        self.conjunto.clear()
        for k in conjuntos:
            self.conjunto.addItem("%s v%s" % (k.get("code"), k.get("version")), k.get("id"))
        self._habilitar()

    def cargar(self, *_):
        en_hilo(servicios.calibraciones, self.c, listo=self._poner, fallo=self.v.mostrar_error)

    def _poner(self, calibraciones):
        self.lista = calibraciones
        elegido = self.actual["id"] if self.actual else None
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        for k in calibraciones:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            valores = (k.get("id"), "%s v%s" % (k.get("dataset_code"), k.get("dataset_version")),
                       estado(k.get("status"))[0], "%s %%" % num(k.get("progress")), k.get("requested_by_username"),
                       fecha(k.get("created_at")))
            for col, valor in enumerate(valores):
                self.tabla.setItem(fila, col, celda(valor, k.get("status") if col == 2 else None))
            if k.get("id") == elegido:
                self.tabla.selectRow(fila)
        self.tabla.blockSignals(False)
        self.nota.setText("%d calibraciones." % len(calibraciones) if calibraciones
                          else "Todavía no hay calibraciones. Lanza una con un conjunto observado.")
        en_curso = any(k.get("status") in EN_CURSO for k in calibraciones)
        if en_curso:
            self.reloj.start(config.SEGUNDOS_COLA * 1000)
        else:
            self.reloj.stop()
        if self.actual and any(k["id"] == self.actual["id"] and k.get("status") != self.actual.get("status")
                               for k in calibraciones):
            self.abrir(self.actual["id"])
        self._habilitar()

    def _elegir(self):
        fila = self.tabla.currentRow()
        if 0 <= fila < len(self.lista):
            self.abrir(self.lista[fila]["id"])

    def abrir(self, calibracion_id):
        self._solicitud += 1
        solicitud = self._solicitud
        en_hilo(_detalle, self.c, calibracion_id,
                listo=lambda datos: self._mostrar(datos, solicitud), fallo=self.v.mostrar_error)

    def _mostrar(self, datos, solicitud):
        if solicitud != self._solicitud:
            return
        self.actual, self.ajuste = datos
        k = self.actual
        r = k.get("config") or {}
        self.resumen.setText(
            "<b>Calibración n.º %s</b> · %s · conjunto %s v%s · motor %s (%s) · método %s (%s)<br>"
            "Muestras %s, semillas %s, cuantil %s, semilla del muestreo %s · huella de la configuración %s<br>%s" % (
                k.get("id"), estado(k.get("status"))[0], _html(k.get("dataset_code")), k.get("dataset_version"),
                _html(k.get("engine")), _html(k.get("engine_version")), _html(k.get("method")),
                _html(k.get("method_version")), r.get("muestras"), r.get("semillas"), r.get("cuantil"),
                r.get("semilla_muestreo"), _html((k.get("huella_configuracion") or "")[:12]),
                ("Error: %s" % _html(k["error"])) if k.get("error") else ""))
        self._poner_estimados(k.get("estimados") or [])
        self._poner_metricas(k.get("metricas") or {})
        if self.ajuste:
            graficas.ajuste(self.grafica, self.ajuste.get("semanas") or [])
            self.pie.setText(_nota(self.ajuste))
        else:
            graficas.sin_datos(self.grafica, "Esta calibración todavía no tiene ajuste")
            self.pie.setText("")
        self._habilitar()

    def _poner_estimados(self, estimados):
        self.estimados.setRowCount(len(estimados))
        for fila, p in enumerate(estimados):
            valores = (p.get("nombre"), num(p.get("mediana"), 3), num(p.get("p5"), 3), num(p.get("p95"), 3),
                       "%s a %s" % (num(p.get("minimo"), 2), num(p.get("maximo"), 2)))
            for col, valor in enumerate(valores):
                self.estimados.setItem(fila, col, celda(valor, alinear_derecha=col > 0))

    def _poner_metricas(self, metricas):
        filas = [(n, metricas.get(clave)) for clave, n in (("calibracion", "Calibración"), ("validacion", "Validación"))
                 if metricas.get(clave)]
        self.metricas.setRowCount(len(filas))
        for fila, (nombre, m) in enumerate(filas):
            r2 = m.get("r2")
            valores = (nombre, m.get("semanas"), num(m.get("rmse"), 1), "—" if r2 is None else num(r2, 2),
                       pct(m.get("cobertura")))
            for col, valor in enumerate(valores):
                self.metricas.setItem(fila, col, celda(valor, alinear_derecha=col > 0))

    def _habilitar(self):
        en_curso = bool(self.actual) and self.actual.get("status") in EN_CURSO
        completa = bool(self.actual) and self.actual.get("status") == "completado"
        self.b_lanzar.setEnabled(self.conjunto.count() > 0 and not self._ocupado)
        self.b_cancelar.setEnabled(en_curso and not self._ocupado)
        self.b_escenario.setEnabled(completa and not self._ocupado)
        self.b_evaluar.setEnabled(self.conjunto.count() > 0 and not self._ocupado)

    def lanzar(self):
        self._empezar("Lanzando…")
        en_hilo(servicios.lanzar_calibracion, self.c, self.conjunto.currentData(), self.muestras.value(),
                self.semillas.value(), self.cuantil.value(), self.semilla_muestreo.value(),
                listo=self._lanzada, fallo=self._fallo)

    def _lanzada(self, k):
        self._terminar("Se encoló la calibración n.º %s." % k.get("id"))
        self.v.accion("lanzó la calibración %s" % k.get("id"))
        self.actual = k
        self.cargar()

    def cancelar(self):
        if not self.actual:
            return
        self._empezar("Cancelando…")
        en_hilo(servicios.cancelar_calibracion, self.c, self.actual["id"], listo=self._cancelada, fallo=self._fallo)

    def _cancelada(self, k):
        self._terminar("Se canceló la calibración n.º %s." % k.get("id"))
        self.v.accion("canceló la calibración %s" % k.get("id"))
        self.abrir(k["id"])
        self.cargar()

    def evaluar(self):
        self._empezar("Evaluando…")
        en_hilo(servicios.evaluar_parametros, self.c, self.conjunto.currentData(), self.r0.value(),
                self.rho.value(), self.phi.value(), listo=self._evaluada, fallo=self._fallo)

    def _evaluada(self, e):
        self._terminar("")
        self._solicitud += 1
        self.actual = None
        self.resumen.setText("<b>Evaluación sin guardar</b> · conjunto %s v%s · motor %s (%s) · R₀ %s, ρ %s, φ %s · "
                             "pérdida %s<br>%s" % (
                                 _html(e.get("dataset_code")), e.get("dataset_version"), _html(e.get("motor")),
                                 _html(e.get("engine_version")), num((e.get("parametros") or {}).get("r0"), 2),
                                 num((e.get("parametros") or {}).get("rho"), 3),
                                 num((e.get("parametros") or {}).get("phi"), 3), num(e.get("perdida"), 2),
                                 _html(e.get("aviso"))))
        self.estimados.setRowCount(0)
        self._poner_metricas(e.get("metricas") or {})
        graficas.ajuste(self.grafica, e.get("semanas") or [])
        self.pie.setText("")
        self._habilitar()

    def crear_escenario(self):
        if not self.actual:
            return
        self._empezar("Creando el borrador…")
        en_hilo(servicios.crear_borrador_calibrado, self.c, self.actual["id"], listo=self._creado, fallo=self._fallo)

    def _creado(self, creado):
        self._terminar("Se creó el escenario n.º %s con %s intervenciones y el R₀ calibrado, en borrador."
                       % (creado["escenario_id"], creado["intervenciones"]))
        self.v.accion("creó el escenario %s desde la calibración" % creado["escenario_id"])
        QMessageBox.information(self, "Escenario calibrado",
                                "El borrador quedó en Escenarios. Revísalo y envíalo a revisión como cualquier otro.")
        self.v.abrir_escenario(creado["escenario_id"], creado["version"].get("version_number"))

    def _empezar(self, texto):
        self._ocupado = True
        self.mensaje.setText(texto)
        self._habilitar()

    def _terminar(self, texto):
        self._ocupado = False
        self.mensaje.setText(texto)
        self._habilitar()

    def _fallo(self, exc):
        self._terminar("")
        if isinstance(exc, api.ErrorServicio) and exc.status in (400, 409, 422, 429):
            self.mensaje.setText("El servidor rechazó la petición: %s" % exc)
            return
        self.v.mostrar_error(exc)


def _nota(ajuste):
    m = (ajuste.get("metricas") or {}).get("validacion") or {}
    cobertura = m.get("cobertura")
    veredicto = ""
    if cobertura is not None:
        veredicto = "En validación la cobertura es %s; el criterio de D50 pide al menos %s. " % (
            pct(cobertura), pct(COBERTURA_MINIMA))
    return veredicto + (ajuste.get("nota") or "")


def _detalle(c, calibracion_id):
    k = servicios.calibracion(c, calibracion_id)
    ajuste = servicios.ajuste_calibracion(c, calibracion_id) if k.get("status") == "completado" else None
    return k, ajuste
