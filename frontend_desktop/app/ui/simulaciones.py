import threading

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QProgressBar, QProgressDialog, QPushButton, QScrollArea,
                               QSpinBox, QTabBar, QVBoxLayout, QWidget)

from .. import api, config, exportar, servicios
from .comun import celda, encabezado, estado, fecha, limpiar, pastilla, sim, tabla, tarjeta
from .tareas import en_hilo

PESTANAS = (("Cola", ("encolado", "ejecutando")), ("Completadas", ("completado",)),
            ("Con error", ("fallido",)), ("Todas", None))
COLORES = {"completado": "#0F172A", "ejecutando": "#3B82F6", "encolado": "#E2E8F0",
           "fallido": "#EF4444", "cancelado": "#F59E0B"}
COLUMNAS = ["Corrida", "Escenario", "Motor", "Semilla", "Estado", "Avance", "Lanzada por", "En cola"]


def _cargar(c, motor):
    corridas = servicios.corridas(c, engine=motor)
    progreso = {x["id"]: servicios.corrida(c, x["id"]).get("progress")
                for x in corridas if x["status"] == "ejecutando"}
    return corridas, progreso


def _aprobadas(c):
    salida = []
    for e in servicios.escenarios(c):
        if e.get("version_status") == "aprobado":
            version = servicios.escenario(c, e["id"])["version"]
            salida.append({"version_id": version["id"], "nombre": "%s · v%s" % (e["name"], e["version_number"])})
    return salida


def _lanzar_lote(c, versiones, replicas, motor, forzar, alto, avance):
    hechas, errores = 0, []
    for v in versiones:
        for semilla in range(1, replicas + 1):
            if alto.is_set():
                return hechas, errores
            try:
                servicios.lanzar_corrida(c, v["version_id"], semilla, motor, forzar)
                hechas += 1
            except api.SesionCerrada:
                raise
            except api.ErrorServicio as exc:
                errores.append("%s, semilla %s: %s" % (v["nombre"], semilla, exc))
            avance(hechas + len(errores), v["nombre"])
    return hechas, errores


def _cancelar(c, ids):
    for corrida_id in ids:
        try:
            servicios.cancelar_corrida(c, corrida_id)
        except api.ErrorServicio as exc:
            if exc.status != 409:
                raise
    return len(ids)


class RejillaReplicas(QWidget):
    LADO = 14

    def __init__(self):
        super().__init__()
        self.corridas = []
        self.setMinimumHeight(self.LADO)

    def poner(self, corridas):
        self.corridas = sorted(corridas, key=lambda x: x["seed"])
        por_fila = max((self.width() or 300) // (self.LADO + 3), 1)
        filas = max((len(self.corridas) + por_fila - 1) // por_fila, 1)
        self.setMinimumHeight(filas * (self.LADO + 3))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        por_fila = max(self.width() // (self.LADO + 3), 1)
        for i, corrida in enumerate(self.corridas):
            x = (i % por_fila) * (self.LADO + 3)
            y = (i // por_fila) * (self.LADO + 3)
            p.fillRect(QRectF(x, y, self.LADO, self.LADO), QColor(COLORES.get(corrida["status"], "#E2E8F0")))
        p.end()


class VistaSimulaciones(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.c = ventana.cliente
        self.corridas = []
        self.progreso = {}
        self.visibles = []
        self.elegida = None
        self.cargando = False
        self.fichas = {}
        self.datos_fichas = {}
        self.pendiente = None
        self.reloj = QTimer(self)
        self.reloj.timeout.connect(self.refrescar)

        exportar_b = QPushButton("Exportar historial")
        exportar_b.clicked.connect(self.exportar_historial)
        cabeza, _ = encabezado("Trabajo", "Simulaciones y cola de trabajos", [exportar_b])

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        cuerpo.addWidget(self._centro(), 1)
        cuerpo.addWidget(self._detalle())
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(cabeza)
        capa.addLayout(cuerpo, 1)

    def _centro(self):
        caja = QWidget()
        capa = QVBoxLayout(caja)
        capa.setContentsMargins(16, 16, 16, 16)
        marco, interior = tarjeta()
        barra = QHBoxLayout()
        self.pestanas = QTabBar()
        for nombre, _ in PESTANAS:
            self.pestanas.addTab(nombre)
        self.pestanas.currentChanged.connect(lambda _: self.pintar())
        self.filtro = QLineEdit()
        self.filtro.setPlaceholderText("Filtrar por escenario o ID")
        self.filtro.setMinimumWidth(120)
        self.filtro.textChanged.connect(lambda _: self.pintar())
        self.motor = QComboBox()
        self.motor.addItem("Motor: todos", "")
        for m in config.MOTORES:
            self.motor.addItem(m, m)
        self.motor.currentIndexChanged.connect(lambda _: self.refrescar())
        barra.addWidget(self.pestanas, 1)
        barra.addWidget(self.filtro)
        barra.addWidget(self.motor)
        interior.addLayout(barra)
        self.tabla = tabla(COLUMNAS, estirar=(1,))
        self.tabla.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.tabla.setColumnWidth(5, 120)
        self.tabla.itemSelectionChanged.connect(self._elegir)
        interior.addWidget(self.tabla, 1)
        self.pie = QLabel()
        self.pie.setObjectName("nota")
        interior.addWidget(self.pie)
        capa.addWidget(marco, 1)
        capa.addWidget(self._lote())
        return caja

    def _lote(self):
        marco, interior = tarjeta("Nuevo lote")
        nota = QLabel("Solo las versiones aprobadas pueden lanzarse. Cada réplica es una corrida con su semilla "
                      "(1..N), la misma en todos los escenarios para que sean comparables.")
        nota.setObjectName("nota")
        nota.setWordWrap(True)
        actualizar = QPushButton("Actualizar versiones")
        actualizar.clicked.connect(self.cargar_aprobadas)
        arriba = QHBoxLayout()
        arriba.addWidget(nota, 1)
        arriba.addWidget(actualizar)
        interior.addLayout(arriba)
        self.contenedor_fichas = QWidget()
        self.capa_fichas = QHBoxLayout(self.contenedor_fichas)
        self.capa_fichas.setContentsMargins(0, 0, 0, 0)
        desplazar = QScrollArea()
        desplazar.setWidgetResizable(True)
        desplazar.setFrameShape(QFrame.NoFrame)
        desplazar.setFixedHeight(48)
        desplazar.setWidget(self.contenedor_fichas)
        interior.addWidget(desplazar)
        fila = QHBoxLayout()
        self.replicas = QSpinBox()
        self.replicas.setRange(1, config.REPLICAS_MAX)
        self.replicas.setValue(config.REPLICAS_DEFECTO)
        self.replicas.valueChanged.connect(lambda _: self._estimar())
        self.motor_lote = QComboBox()
        for m in config.MOTORES:
            self.motor_lote.addItem(m)
        self.forzar = QCheckBox("Forzar error (prueba)")
        self.estimacion = QLabel()
        self.estimacion.setObjectName("nota")
        self.estimacion.setWordWrap(True)
        self.encolar = QPushButton("Encolar")
        self.encolar.setObjectName("primario")
        self.encolar.clicked.connect(self.lanzar)
        fila.addWidget(QLabel("Réplicas"))
        fila.addWidget(self.replicas)
        fila.addWidget(QLabel("Motor"))
        fila.addWidget(self.motor_lote)
        fila.addWidget(self.forzar)
        fila.addWidget(self.estimacion, 1)
        fila.addWidget(self.encolar)
        interior.addLayout(fila)
        return marco

    def _detalle(self):
        marco = QFrame()
        marco.setObjectName("panel")
        marco.setFixedWidth(300)
        capa = QVBoxLayout(marco)
        self.d_titulo = QLabel("Elige una corrida")
        self.d_titulo.setObjectName("tituloTarjeta")
        self.d_titulo.setWordWrap(True)
        self.d_estado = QHBoxLayout()
        self.d_cifra = QLabel("")
        self.d_cifra.setObjectName("cifra")
        self.d_barra = QProgressBar()
        self.d_barra.setTextVisible(False)
        self.d_replicas = QLabel("Réplicas de la versión")
        self.d_replicas.setObjectName("etiquetaDato")
        self.rejilla = RejillaReplicas()
        leyenda = QLabel('<span style="color:#0F172A">■</span> Completa  <span style="color:#3B82F6">■</span> '
                         'En curso  <span style="color:#CBD5E1">■</span> En espera  '
                         '<span style="color:#EF4444">■</span> Error')
        leyenda.setObjectName("nota")
        self.d_forma = QFormLayout()
        self.d_campos = {}
        for clave, texto in (("seed", "Semilla"), ("engine", "Motor"), ("version", "Versión"),
                             ("requested_by_username", "Lanzada por"), ("queued_at", "En cola"),
                             ("started_at", "Inicio"), ("finished_at", "Fin")):
            etiqueta = QLabel("—")
            self.d_campos[clave] = etiqueta
            self.d_forma.addRow(texto, etiqueta)
        self.d_error = QLabel()
        self.d_error.setWordWrap(True)
        self.d_error.setStyleSheet("color: #B91C1C;")
        self.b_cancelar = QPushButton("Cancelar corrida")
        self.b_cancelar.setObjectName("peligro")
        self.b_cancelar.clicked.connect(self.cancelar)
        self.b_cancelar_lote = QPushButton("Cancelar las en espera de esta versión")
        self.b_cancelar_lote.clicked.connect(self.cancelar_lote)
        self.b_comparar = QPushButton("Comparar esta versión")
        self.b_comparar.clicked.connect(self.comparar)
        reproducibilidad = QLabel("Reproducibilidad")
        reproducibilidad.setObjectName("tituloTarjeta")
        capa.addWidget(self.d_titulo)
        capa.addLayout(self.d_estado)
        capa.addWidget(self.d_cifra)
        capa.addWidget(self.d_barra)
        capa.addWidget(self.d_replicas)
        capa.addWidget(self.rejilla)
        capa.addWidget(leyenda)
        capa.addWidget(reproducibilidad)
        capa.addLayout(self.d_forma)
        capa.addWidget(self.d_error)
        capa.addStretch(1)
        for b in (self.b_cancelar, self.b_cancelar_lote, self.b_comparar):
            capa.addWidget(b)
        self._mostrar_detalle()
        return marco

    def al_mostrar(self):
        self.forzar.setVisible(self.v.es_admin())
        self.forzar.setChecked(False)
        self.refrescar()
        if not self.fichas:
            self.cargar_aprobadas()
        self.reloj.start(config.SEGUNDOS_COLA * 1000)

    def hideEvent(self, evento):
        self.reloj.stop()
        super().hideEvent(evento)

    def refrescar(self):
        if self.cargando or self.v.reingresando:
            return
        self.cargando = True
        en_hilo(_cargar, self.c, self.motor.currentData(), listo=self._cargado, fallo=self._fallo_carga)

    def _fallo_carga(self, exc):
        self.cargando = False
        self.reloj.stop()
        self.v.mostrar_error(exc)

    def _cargado(self, resultado):
        self.cargando = False
        self.corridas, self.progreso = resultado
        self.v.mostrar_cola(self.corridas)
        for i, (nombre, estados) in enumerate(PESTANAS):
            n = len([x for x in self.corridas if estados is None or x["status"] in estados])
            self.pestanas.setTabText(i, "%s · %d" % (nombre, n))
        self.pintar()

    def _avance(self, corrida):
        if corrida["status"] == "completado":
            return 100
        if corrida["status"] == "ejecutando":
            return self.progreso.get(corrida["id"]) or 0
        return 0

    def _barra(self, avance):
        caja = QWidget()
        capa = QVBoxLayout(caja)
        capa.setContentsMargins(8, 11, 8, 11)
        barra = QProgressBar()
        barra.setValue(avance)
        barra.setTextVisible(False)
        capa.addWidget(barra)
        return caja

    def pintar(self):
        estados = PESTANAS[self.pestanas.currentIndex()][1]
        texto = self.filtro.text().strip().lower()
        self.visibles = [x for x in self.corridas if (estados is None or x["status"] in estados)
                         and (not texto or texto in (x.get("scenario_name") or "").lower()
                              or texto in sim(x["id"]).lower() or texto == str(x["id"]))]
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        for x in self.visibles:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            valores = (sim(x["id"]), "%s · v%s" % (x.get("scenario_name"), x.get("version_number")),
                       x.get("engine"), x.get("seed"), estado(x["status"])[0], None,
                       x.get("requested_by_username"), fecha(x.get("queued_at")))
            for col, valor in enumerate(valores):
                if col == 5:
                    self.tabla.setCellWidget(fila, col, self._barra(self._avance(x)))
                    continue
                self.tabla.setItem(fila, col, celda(valor, x["status"] if col == 4 else None,
                                                    dato=x["id"] if col == 0 else None))
            if x["id"] == self.elegida:
                self.tabla.selectRow(fila)
        self.tabla.blockSignals(False)
        self.pie.setText("Mostrando %d de %d corridas (las %d más recientes que da el servicio). "
                         "Se actualiza cada %d s." % (len(self.visibles), len(self.corridas),
                                                      len(self.corridas), config.SEGUNDOS_COLA))
        self._mostrar_detalle()

    def _elegir(self):
        fila = self.tabla.currentRow()
        if 0 <= fila < len(self.visibles):
            self.elegida = self.visibles[fila]["id"]
            self._mostrar_detalle()

    def _corrida_elegida(self):
        return next((x for x in self.corridas if x["id"] == self.elegida), None)

    def _mostrar_detalle(self):
        x = self._corrida_elegida()
        limpiar(self.d_estado)
        for b in (self.b_cancelar, self.b_cancelar_lote, self.b_comparar):
            b.setEnabled(x is not None)
        if x is None:
            self.d_titulo.setText("Elige una corrida")
            self.d_cifra.setText("")
            self.d_barra.setValue(0)
            self.rejilla.poner([])
            return
        self.d_titulo.setText("%s · %s" % (sim(x["id"]), x.get("scenario_name")))
        self.d_estado.addWidget(pastilla(x["status"]))
        self.d_estado.addStretch(1)
        avance = self._avance(x)
        self.d_cifra.setText("%d%%" % avance)
        self.d_barra.setValue(avance)
        hermanas = [y for y in self.corridas if y["scenario_version_id"] == x["scenario_version_id"]
                    and y.get("engine") == x.get("engine")]
        hechas = sum(1 for y in hermanas if y["status"] == "completado")
        self.d_replicas.setText("Réplicas de la versión: %d de %d completas" % (hechas, len(hermanas)))
        self.rejilla.poner(hermanas)
        for clave, etiqueta in self.d_campos.items():
            if clave == "version":
                etiqueta.setText("v%s · id %s" % (x.get("version_number"), x.get("scenario_version_id")))
            elif clave.endswith("_at"):
                etiqueta.setText(fecha(x.get(clave)))
            else:
                etiqueta.setText(str(x.get(clave) or "—"))
        self.d_error.setText(x.get("error_message") or "")
        self.b_cancelar.setEnabled(x["status"] == "encolado")
        self.b_cancelar_lote.setEnabled(any(y["status"] == "encolado" for y in hermanas))

    def cancelar(self):
        x = self._corrida_elegida()
        if x and QMessageBox.question(self, "Cancelar", "¿Cancelar %s?" % sim(x["id"])) == QMessageBox.Yes:
            self.v.accion("cancela la corrida %s" % x["id"])
            en_hilo(_cancelar, self.c, [x["id"]], listo=lambda _: self.refrescar())

    def cancelar_lote(self):
        x = self._corrida_elegida()
        ids = [y["id"] for y in self.corridas
               if y["scenario_version_id"] == x["scenario_version_id"] and y["status"] == "encolado"]
        pregunta = "¿Cancelar las %d corridas en espera de %s · v%s?" % (len(ids), x.get("scenario_name"),
                                                                       x.get("version_number"))
        if ids and QMessageBox.question(self, "Cancelar", pregunta) == QMessageBox.Yes:
            self.v.accion("cancela %d corridas de la versión %s" % (len(ids), x["scenario_version_id"]))
            en_hilo(_cancelar, self.c, ids, listo=lambda _: self.refrescar())

    def comparar(self):
        x = self._corrida_elegida()
        self.v.comparar([{"version_id": x["scenario_version_id"],
                          "nombre": "%s · v%s" % (x.get("scenario_name"), x.get("version_number"))}])

    def cargar_aprobadas(self):
        en_hilo(_aprobadas, self.c, listo=self._aprobadas)

    def _aprobadas(self, versiones):
        marcadas = {vid for vid, b in self.fichas.items() if b.isChecked()}
        limpiar(self.capa_fichas)
        self.fichas = {}
        self.datos_fichas = {}
        for v in versiones + ([self.pendiente] if self.pendiente else []):
            if v["version_id"] in self.fichas:
                continue
            boton = QPushButton(v["nombre"])
            boton.setObjectName("ficha")
            boton.setCheckable(True)
            boton.setChecked(v["version_id"] in marcadas or v == self.pendiente)
            self.datos_fichas[v["version_id"]] = v
            boton.toggled.connect(lambda _: self._estimar())
            self.fichas[v["version_id"]] = boton
            self.capa_fichas.addWidget(boton)
        if not self.fichas:
            self.capa_fichas.addWidget(QLabel("No hay versiones aprobadas. Un epidemiólogo las aprueba en la web."))
        self.capa_fichas.addStretch(1)
        self.pendiente = None
        self._estimar()

    def preseleccionar(self, version):
        if version["version_id"] in self.fichas:
            self.fichas[version["version_id"]].setChecked(True)
        else:
            self.pendiente = version
            self.cargar_aprobadas()

    def _elegidas(self):
        return [self.datos_fichas[vid] for vid, b in self.fichas.items() if b.isChecked()]

    def _estimar(self):
        n = len(self._elegidas())
        self.estimacion.setText("%d escenarios × %d réplicas = %d corridas" % (n, self.replicas.value(),
                                                                               n * self.replicas.value()))
        self.encolar.setText("Encolar %d escenarios" % n if n else "Encolar")
        self.encolar.setEnabled(n > 0)

    def lanzar(self):
        versiones = self._elegidas()
        replicas = self.replicas.value()
        if replicas < config.REPLICAS_DEFECTO:
            pregunta = ("¿Seguro que quieres bajar de %d réplicas? Con menos réplicas la comparación entre "
                        "escenarios es menos confiable (D8)." % config.REPLICAS_DEFECTO)
            if QMessageBox.question(self, "Réplicas", pregunta) != QMessageBox.Yes:
                return
        total = len(versiones) * replicas
        alto = threading.Event()
        dialogo = QProgressDialog("Encolando corridas…", "Detener", 0, total, self)
        dialogo.setWindowModality(Qt.WindowModal)
        dialogo.setMinimumDuration(0)
        dialogo.canceled.connect(alto.set)
        motor = self.motor_lote.currentText()
        forzar = self.forzar.isChecked() and self.v.es_admin()
        self.v.accion("encola %d corridas (%d réplicas, motor %s) de las versiones %s"
                      % (total, replicas, motor, [v["version_id"] for v in versiones]))

        def avance(hechas, nombre):
            dialogo.setValue(hechas)
            dialogo.setLabelText("Encolando %s (%d de %d)…" % (nombre, hechas, total))

        def listo(resultado):
            dialogo.close()
            hechas, errores = resultado
            texto = "Se encolaron %d de %d corridas." % (hechas, total)
            if errores:
                texto += "\n\nFallaron %d:\n%s" % (len(errores), "\n".join(errores[:10]))
            QMessageBox.information(self, "Nuevo lote", texto)
            self.pestanas.setCurrentIndex(0)
            self.refrescar()

        def fallo(exc):
            dialogo.close()
            self.v.mostrar_error(exc)

        en_hilo(_lanzar_lote, self.c, versiones, replicas, motor, forzar, alto,
                listo=listo, fallo=fallo, avance=avance)

    def exportar_historial(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar historial", "corridas.csv", "CSV (*.csv)")
        if not ruta:
            return
        filas = [(sim(x["id"]), x.get("scenario_name"), x.get("version_number"), x.get("engine"), x.get("seed"),
                  x["status"], x.get("requested_by_username"), x.get("queued_at"), x.get("started_at"),
                  x.get("finished_at"), x.get("error_message")) for x in self.visibles]
        exportar.guardar_csv(ruta, ["corrida", "escenario", "version", "motor", "semilla", "estado",
                                    "lanzada_por", "en_cola", "inicio", "fin", "error"], filas)
        self.v.accion("exporta %d corridas a %s" % (len(filas), ruta))
        QMessageBox.information(self, "Exportar", "Se guardaron %d corridas en %s." % (len(filas), ruta))
