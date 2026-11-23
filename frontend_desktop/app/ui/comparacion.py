from html import escape

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QScrollArea, QTabWidget, QVBoxLayout, QWidget)

from .. import config, exportar, resumen, servicios
from . import graficas
from .comun import celda, encabezado, limpiar, num, pct, sim, tabla, tarjeta
from .corrida import DialogoCorrida
from .tareas import en_hilo


def _con_resultados(c):
    versiones = {}
    for x in servicios.corridas(c, status="completado"):
        v = versiones.setdefault(x["scenario_version_id"], {
            "version_id": x["scenario_version_id"],
            "nombre": "%s · v%s" % (x.get("scenario_name"), x.get("version_number")), "n": 0})
        v["n"] += 1
    return sorted(versiones.values(), key=lambda v: v["nombre"])


def _rango(s, decimales=0, como_pct=False):
    if not s:
        return "—"
    f = (lambda x: pct(x, decimales)) if como_pct else (lambda x: num(x, decimales))
    return "%s (%s–%s)" % (f(s["mediana"]), f(s["p5"]), f(s["p95"]))


class VistaComparacion(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.c = ventana.cliente
        self.elegidas = []
        self.datos = None
        self.seleccion = 0
        self._comparando = False

        self.reporte = None
        self._subiendo = False
        self.b_csv = QPushButton("Exportar CSV")
        self.b_pdf = QPushButton("Exportar PDF")
        self.b_subir = QPushButton("Subir reporte")
        self.b_subir.setToolTip("Guarda el PDF de esta comparación en el almacenamiento del sistema (RF-F17).")
        self.b_url = QPushButton("Abrir reporte subido")
        self.b_url.setToolTip("Abre el PDF guardado con un enlace que vence en 15 minutos.")
        self.b_imprimir = QPushButton("Imprimir")
        self.b_imprimir.setObjectName("primario")
        self.b_csv.clicked.connect(self.exportar_csv)
        self.b_pdf.clicked.connect(self.exportar_pdf)
        self.b_subir.clicked.connect(self.subir_reporte)
        self.b_url.clicked.connect(self.abrir_reporte)
        self.b_imprimir.clicked.connect(self.imprimir)
        cabeza, _ = encabezado("Trabajo", "Comparación de escenarios",
                               (self.b_csv, self.b_pdf, self.b_subir, self.b_url, self.b_imprimir))

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        cuerpo.addWidget(self._centro(), 1)
        cuerpo.addWidget(self._panel())
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(cabeza)
        capa.addLayout(cuerpo, 1)
        self._habilitar()

    def _centro(self):
        contenido = QWidget()
        contenido.setObjectName("contenido")
        capa = QVBoxLayout(contenido)
        capa.setContentsMargins(16, 16, 16, 16)

        marco, interior = tarjeta()
        fichas = QWidget()
        fichas.setObjectName("fichasComparacion")
        self.capa_fichas = QHBoxLayout(fichas)
        self.capa_fichas.setContentsMargins(0, 0, 0, 0)
        desplazar = QScrollArea()
        desplazar.setWidgetResizable(True)
        desplazar.setFrameShape(QFrame.NoFrame)
        desplazar.setFixedHeight(48)
        desplazar.viewport().setStyleSheet("background-color: #FFFFFF;")
        desplazar.setWidget(fichas)
        interior.addWidget(desplazar)
        fila = QHBoxLayout()
        self.disponibles = QComboBox()
        self.disponibles.setMinimumWidth(200)
        agregar = QPushButton("+ Agregar versión")
        agregar.clicked.connect(lambda: self.agregar([self.disponibles.currentData()]))
        recargar = QPushButton("Actualizar")
        recargar.clicked.connect(self.cargar_disponibles)
        self.metrica = QComboBox()
        for clave, texto in resumen.METRICAS:
            self.metrica.addItem(texto, clave)
        self.motor = QComboBox()
        self.motor.addItem("Todos", "")
        for motor in config.MOTORES:
            self.motor.addItem(motor, motor)
        self.b_comparar = QPushButton("Comparar")
        self.b_comparar.setObjectName("primario")
        self.b_comparar.clicked.connect(self.comparar)
        fila.addWidget(self.disponibles, 1)
        fila.addWidget(agregar)
        fila.addWidget(recargar)
        fila.addWidget(QLabel("Métrica"))
        fila.addWidget(self.metrica)
        fila.addWidget(self.b_comparar)
        interior.addLayout(fila)
        filtro = QHBoxLayout()
        filtro.addWidget(QLabel("Motor"))
        filtro.addWidget(self.motor)
        filtro.addWidget(QLabel("Usa un solo motor para comparar escenarios bajo el mismo modelo."))
        filtro.addStretch(1)
        interior.addLayout(filtro)
        capa.addWidget(marco)

        graficas_fila = QHBoxLayout()
        izquierda, capa_izq = tarjeta("Frontera de eficiencia")
        nota = QLabel("Eje X: personas-día; eje Y: impacto en personas simuladas. Punto: mediana; barra: p5–p95.")
        nota.setObjectName("nota")
        nota.setWordWrap(True)
        self.g_frontera = graficas.vista()
        capa_izq.addWidget(nota)
        capa_izq.addWidget(self.g_frontera)
        derecha, capa_der = tarjeta("Casos activos superpuestos")
        nota = QLabel("Casos activos en personas simuladas. Selecciona un escenario para ver su banda p5–p95.")
        nota.setObjectName("nota")
        nota.setWordWrap(True)
        self.g_curvas = graficas.vista()
        capa_der.addWidget(nota)
        capa_der.addWidget(self.g_curvas)
        graficas_fila.addWidget(izquierda)
        graficas_fila.addWidget(derecha)
        capa.addLayout(graficas_fila)

        self.fuentes = QLabel()
        self.fuentes.setObjectName("nota")
        self.fuentes.setTextFormat(Qt.PlainText)
        self.fuentes.setWordWrap(True)
        capa.addWidget(self.fuentes)

        pestanas = QTabWidget()
        indicadores, capa_ind = tarjeta()
        self.nota_tabla = QLabel()
        self.nota_tabla.setObjectName("nota")
        self.tabla = tabla(["Escenario", "Réplicas", "Muertes", "Pico de casos activos", "Día del pico",
                            "Tasa de ataque", "Personas-día", "Costo (MXN)", "Frontera"], estirar=(0, 8))
        self.tabla.setMinimumHeight(180)
        self.tabla.itemSelectionChanged.connect(self._elegir)
        capa_ind.addWidget(self.nota_tabla)
        capa_ind.addWidget(self.tabla)
        pestanas.addTab(indicadores, "Indicadores")
        diferencias, capa_dif = tarjeta()
        linea_base = QHBoxLayout()
        self.referencia = QComboBox()
        self.referencia.currentIndexChanged.connect(self._pintar_diferencias)
        linea_base.addWidget(QLabel("Escenario de referencia"))
        linea_base.addWidget(self.referencia, 1)
        capa_dif.addLayout(linea_base)
        nota = QLabel(resumen.METODO_DIFERENCIAS)
        nota.setWordWrap(True)
        nota.setObjectName("nota")
        capa_dif.addWidget(nota)
        self.diferencias = tabla(["Escenario", "Indicador", "Unidad", "Diferencia absoluta", "Diferencia relativa"],
                                 estirar=(0, 1))
        self.diferencias.setMinimumHeight(180)
        capa_dif.addWidget(self.diferencias)
        pestanas.addTab(diferencias, "Diferencias")

        costos, capa_costos = tarjeta()
        self.modelo_costo = QLabel("Compara escenarios para consultar el modelo de costos.")
        self.modelo_costo.setTextFormat(Qt.PlainText)
        self.modelo_costo.setWordWrap(True)
        capa_costos.addWidget(self.modelo_costo)
        self.costos = tabla(["Tipo", "Valor", "Unidad", "Fuente", "Estado"], estirar=(0, 3))
        capa_costos.addWidget(self.costos)
        pestanas.addTab(costos, "Supuestos de costos")
        capa.addWidget(pestanas)

        self.aviso = QLabel("Agrega al menos dos versiones con corridas completadas y pulsa Comparar.")
        self.aviso.setObjectName("aviso")
        self.aviso.setTextFormat(Qt.PlainText)
        self.aviso.setWordWrap(True)
        capa.addWidget(self.aviso)
        desplazar = QScrollArea()
        desplazar.setWidgetResizable(True)
        desplazar.setFrameShape(QFrame.NoFrame)
        desplazar.setWidget(contenido)
        return desplazar

    def _panel(self):
        marco = QFrame()
        marco.setObjectName("panel")
        marco.setFixedWidth(300)
        capa = QVBoxLayout(marco)
        titulo = QLabel("Lectura de la frontera")
        titulo.setObjectName("tituloTarjeta")
        self.lectura = QLabel("—")
        self.lectura.setTextFormat(Qt.PlainText)
        self.lectura.setWordWrap(True)
        seleccionado = QLabel("Seleccionado")
        seleccionado.setObjectName("tituloTarjeta")
        self.detalle = QLabel("—")
        self.detalle.setWordWrap(True)
        self.detalle.setTextFormat(Qt.RichText)
        self.replicas = QComboBox()
        self.b_ficha = QPushButton("Abrir ficha de la corrida")
        self.b_ficha.setEnabled(False)
        self.b_ficha.clicked.connect(self.abrir_ficha)
        pie = QLabel("Elegir entre los escenarios de la frontera es una decisión humana; este análisis no "
                     "recomienda ninguno ni constituye asesoría sanitaria.")
        pie.setObjectName("nota")
        pie.setWordWrap(True)
        capa.addWidget(titulo)
        capa.addWidget(self.lectura)
        capa.addSpacing(12)
        capa.addWidget(seleccionado)
        capa.addWidget(self.detalle)
        capa.addWidget(QLabel("Réplicas de la curva seleccionada"))
        capa.addWidget(self.replicas)
        capa.addWidget(self.b_ficha)
        capa.addStretch(1)
        capa.addWidget(pie)
        return marco

    def al_mostrar(self):
        if self.disponibles.count() == 0:
            self.cargar_disponibles()

    def cargar_disponibles(self):
        en_hilo(_con_resultados, self.c, listo=self._disponibles)

    def _disponibles(self, versiones):
        self.disponibles.clear()
        for v in versiones:
            self.disponibles.addItem("%s · %d corridas completadas" % (v["nombre"], v["n"]), v)
        if not versiones:
            self.disponibles.addItem("Sin corridas completadas todavía", None)

    def agregar(self, versiones):
        for v in versiones:
            if v and all(e["version_id"] != v["version_id"] for e in self.elegidas):
                self.elegidas.append({"version_id": v["version_id"], "nombre": v["nombre"]})
        self._fichas()

    def quitar(self, version_id):
        self.elegidas = [e for e in self.elegidas if e["version_id"] != version_id]
        self._fichas()

    def _fichas(self):
        limpiar(self.capa_fichas)
        self.capa_fichas.addWidget(QLabel("Comparando %d escenarios:" % len(self.elegidas)))
        for i, e in enumerate(self.elegidas):
            boton = QPushButton("%s  ✕" % e["nombre"])
            boton.setObjectName("ficha")
            boton.setStyleSheet("border-left: 4px solid %s;" % graficas.COLORES[i % len(graficas.COLORES)])
            boton.clicked.connect(lambda _=False, vid=e["version_id"]: self.quitar(vid))
            self.capa_fichas.addWidget(boton)
        self.capa_fichas.addStretch(1)
        self._habilitar()

    def _habilitar(self):
        self.b_comparar.setEnabled(len(self.elegidas) >= 2 and not self._comparando)
        for b in (self.b_csv, self.b_pdf, self.b_imprimir):
            b.setEnabled(self.datos is not None and not self._comparando)
        self.b_subir.setEnabled(self.datos is not None and not self._comparando and not self._subiendo)
        self.b_url.setEnabled(self.reporte is not None and not self._subiendo)

    def comparar(self):
        if self._comparando or len(self.elegidas) < 2:
            return
        self._comparando = True
        self._habilitar()
        self.b_comparar.setText("Comparando…")
        ids = [e["version_id"] for e in self.elegidas]
        self.v.accion("compara las versiones %s" % ids)
        en_hilo(servicios.cargar_comparacion, self.c, ids, self.metrica.currentData(), self.motor.currentData(),
                listo=self._mostrar, fallo=self._fallo)

    def _fallo(self, exc):
        self._comparando = False
        self.b_comparar.setText("Comparar")
        self._habilitar()
        self.v.mostrar_error(exc)

    def _mostrar(self, datos):
        self._comparando = False
        self.datos = datos
        self.reporte = None
        self.seleccion = 0
        self.b_comparar.setText("Comparar")
        self._habilitar()
        semillas = datos["semillas"]
        self.nota_tabla.setText("Mediana (p5–p95) de %d réplicas por escenario, semillas %s a %s comunes a todos."
                                % (len(semillas), semillas[0], semillas[-1]))
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        for e in datos["escenarios"]:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            ind = e["indicadores"]
            valores = (e["nombre"], e["n"], _rango(ind["fallecimientos"]), _rango(ind["pico_casos_activos"]),
                       _rango(ind["dia_pico"]), _rango(ind["tasa_ataque"], 0, True), num(e["costo"]),
                       "Sin dato" if e.get("costo_pesos") is None else "$" + num(e["costo_pesos"], 2),
                       exportar.texto_frontera(e))
            for col, valor in enumerate(valores):
                clave = None
                if col == 8:
                    clave = "aprobado" if e["dominado_por"] == [] else "borrador"
                self.tabla.setItem(fila, col, celda(valor, clave))
        self.tabla.blockSignals(False)
        self.tabla.selectRow(0)
        anterior = self.referencia.currentData()
        self.referencia.blockSignals(True)
        self.referencia.clear()
        for escenario in datos["escenarios"]:
            self.referencia.addItem(escenario["nombre"], escenario.get("version_id"))
        self.referencia.setCurrentIndex(max(0, self.referencia.findData(anterior)))
        self.referencia.blockSignals(False)
        self._pintar_diferencias()
        trazas = datos["trazabilidad_costos"]
        self.modelo_costo.setText("Modelo: %s. Fuente: Pareto. Los pesos se muestran aparte de personas-día.%s"
                                 % (datos.get("modelo_costo") or "Sin dato",
                                    "" if trazas else " El servicio no informó supuestos de costos."))
        self.costos.setRowCount(len(trazas))
        for fila, traza in enumerate(trazas):
            for col, campo in enumerate(("tipo", "valor", "unidad", "fuente", "estado")):
                self.costos.setItem(fila, col, celda(traza.get(campo)))
        supuestos = "Modelo de costo: %s." % (datos.get("modelo_costo") or "—")
        sin_fuente = [c["tipo"] for c in datos["trazabilidad_costos"] if c.get("estado") != "con_fuente"]
        if sin_fuente:
            supuestos += " Costos sin fuente o marcados como supuesto: %s." % ", ".join(sin_fuente)
        for aviso in datos["avisos"]:
            supuestos += " " + aviso
        if len(resumen.modelos_corridas(datos["escenarios"])) > 1:
            supuestos += " Las réplicas incluyen distintos motores o versiones. La diferencia es descriptiva."
        if len(resumen.horizontes_corridas(datos["escenarios"])) > 1:
            supuestos += " Los indicadores incluyen distintos horizontes de simulación."
        bandas = resumen.avisos_bandas(datos["escenarios"])
        advertencia = ""
        if bandas:
            metrica = dict(resumen.METRICAS).get(datos["metrica"], datos["metrica"])
            advertencia = ("\n\nAdvertencia p5–p95 (%s):\n%s\n"
                           "La superposición de intervalos no demuestra que los resultados sean equivalentes."
                           % (metrica, "\n".join("• " + mensaje for mensaje in bandas)))
        self.aviso.setText("%s%s\n\nSupuestos: %s" % (datos["aviso"], advertencia, supuestos))
        self._lectura()
        self._pintar()

    def _lectura(self):
        escenarios = self.datos["escenarios"]
        if all(e["costo"] is None for e in escenarios):
            self.lectura.setText("No hay frontera: el servicio pareto no calculó personas-día.\n\n"
                                 + "\n".join("• " + a for a in self.datos["avisos"]))
            return
        frente = [e["nombre"] for e in escenarios if e["dominado_por"] == []]
        lineas = ["%d de %d escenarios están en la frontera: %s." % (len(frente), len(escenarios), ", ".join(frente))]
        for e in escenarios:
            if e["dominado_por"]:
                lineas.append("%s tiene igual o más %s con igual o más personas-día que %s." % (
                    e["nombre"], dict(resumen.METRICAS)[self.datos["metrica"]].lower(),
                    ", ".join(e["dominado_por"])))
            elif e["dominado_por"] is None:
                lineas.append("%s no tiene personas-día calculadas y queda fuera de la frontera." % e["nombre"])
        self.lectura.setText("\n\n".join(lineas))

    def _pintar(self):
        escenarios = self.datos["escenarios"]
        nombre = dict(resumen.METRICAS)[self.datos["metrica"]]
        if all(resumen.trazable(e) for e in escenarios if e["impacto"] and e["costo"] is not None):
            graficas.frontera(self.g_frontera, escenarios, nombre)
        else:
            graficas.sin_datos(self.g_frontera, "Falta identificar el motor, su versión o el periodo")
        if any(resumen.trazable(e) and e["curva"] for e in escenarios):
            graficas.curvas(self.g_curvas, escenarios, self.seleccion, self.tabla.selectRow)
        else:
            graficas.sin_datos(self.g_curvas, "No hay curvas con motor, versión y serie identificados")
        fuentes = "Fuentes: comparación (series e indicadores), corridas (motor) y Pareto (costos). "
        omitidos = [e["nombre"] for e in escenarios if not resumen.trazable(e)]
        if omitidos:
            fuentes += "Sin gráfica por falta de motor, versión o periodo: %s. " % ", ".join(omitidos)
        self.fuentes.setText(fuentes + resumen.fuentes_graficas(escenarios))
        e = escenarios[self.seleccion]
        self.replicas.clear()
        for r in e.get("replicas", []):
            self.replicas.addItem("%s · Semilla %s" % (sim(r["id"]), r.get("seed", "—")), r)
        self.b_ficha.setEnabled(self.replicas.count() > 0)
        ind = e["indicadores"]
        filas = [("Réplicas", e["n"]),
                 ("Muertes (media)", num(ind["fallecimientos"]["media"]) if ind["fallecimientos"] else "—"),
                 ("Muertes", _rango(ind["fallecimientos"])),
                 ("Pico de casos activos", _rango(ind["pico_casos_activos"])),
                 ("Día del pico", _rango(ind["dia_pico"])),
                 ("Tasa de ataque", _rango(ind["tasa_ataque"], 1, True)),
                 ("Personas-día (mediana)", num(e["costo"])),
                 ("Costo (MXN)", "Sin dato" if e.get("costo_pesos") is None else "$" + num(e["costo_pesos"], 2)),
                 ("Frontera", exportar.texto_frontera(e))]
        self.detalle.setText("<b>%s</b><br>%s" % (escape(e["nombre"]), "<br>".join(
            '<span style="color:#64748B">%s:</span> %s' % (etiqueta, escape(str(valor)))
            for etiqueta, valor in filas)))

    def _pintar_diferencias(self):
        if self.datos is None or self.referencia.currentIndex() < 0:
            return
        self.diferencias.setRowCount(0)
        for valores in exportar.filas_diferencias(self.datos, self.referencia.currentIndex()):
            fila = self.diferencias.rowCount()
            self.diferencias.insertRow(fila)
            for col, valor in enumerate(valores):
                self.diferencias.setItem(fila, col, celda(valor))

    def _elegir(self):
        fila = self.tabla.currentRow()
        if self.datos and 0 <= fila < len(self.datos["escenarios"]) and fila != self.seleccion:
            self.seleccion = fila
            self._pintar()

    def abrir_ficha(self):
        corrida = self.replicas.currentData()
        if corrida:
            DialogoCorrida(self, self.v, corrida).open()

    def _imagenes(self):
        return {"frontera.png": self.g_frontera.grab().toImage(), "curvas.png": self.g_curvas.grab().toImage()}

    def _html(self, imagenes):
        usuario = (self.c.usuario or {}).get("full_name") or self.c.nombre_usuario()
        return exportar.reporte_html(self.datos, usuario, list(imagenes), self.referencia.currentIndex())

    def exportar_csv(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "comparacion.csv", "CSV (*.csv)")
        if ruta:
            try:
                rutas = exportar.csv_comparacion(ruta, self.datos, self.referencia.currentIndex())
            except OSError:
                self.v.mostrar_error(OSError("No se pudo guardar la exportación CSV. Revisa la ubicación."))
                return
            tabla_ruta = rutas[0]
            self.v.accion("exporta la comparación a %s" % tabla_ruta)
            QMessageBox.information(self, "Exportar", "Se guardaron:\n" + "\n".join(map(str, rutas)))

    def exportar_pdf(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar PDF", "comparacion.pdf", "PDF (*.pdf)")
        if ruta:
            imagenes = self._imagenes()
            try:
                exportar.guardar_pdf(ruta, self._html(imagenes), imagenes)
            except OSError:
                self.v.mostrar_error(
                    OSError("No se pudo guardar el reporte PDF. Elige otra ubicación e inténtalo de nuevo.")
                )
                return
            self.v.accion("exporta el reporte de comparación a %s" % ruta)
            QMessageBox.information(self, "Exportar", "Reporte guardado en %s." % ruta)

    def subir_reporte(self):
        if self.datos is None or self._subiendo:
            return
        imagenes = self._imagenes()
        try:
            pdf = exportar.pdf_en_memoria(self._html(imagenes), imagenes)
        except OSError as exc:
            self.v.mostrar_error(exc)
            return
        titulo = "Comparación: " + ", ".join(e["nombre"] for e in self.datos["escenarios"])
        self._subiendo = True
        self._habilitar()
        self.b_subir.setText("Subiendo…")
        en_hilo(servicios.subir_reporte, self.c, exportar.corridas_del_reporte(self.datos), titulo, pdf,
                listo=self._subido, fallo=self._fallo_subida)

    def _subido(self, reporte):
        self._subiendo = False
        self.reporte = reporte
        self.b_subir.setText("Subir reporte")
        self._habilitar()
        self.v.accion("subió el reporte de comparación %s" % reporte.get("id"))
        QMessageBox.information(self, "Reporte", "Reporte %s guardado (%s KB, huella %s…). Ábrelo con «Abrir "
                                "reporte subido»." % (reporte.get("id"), num((reporte.get("size_bytes") or 0) / 1024),
                                                      (reporte.get("sha256") or "")[:12]))

    def _fallo_subida(self, exc):
        self._subiendo = False
        self.b_subir.setText("Subir reporte")
        self._habilitar()
        self.v.mostrar_error(exc)

    def abrir_reporte(self):
        if self.reporte:
            en_hilo(servicios.url_reporte, self.c, self.reporte["id"], listo=self._abrir_url, fallo=self.v.mostrar_error)

    def _abrir_url(self, datos):
        url = datos.get("url") or ""
        if not url.startswith(("https://", "http://")):
            self.v.mostrar_error(OSError("El servidor no devolvió un enlace válido para el reporte."))
            return
        QDesktopServices.openUrl(QUrl(url))
        self.v.accion("abrió el reporte %s" % self.reporte.get("id"))

    def imprimir(self):
        impresora = QPrinter(QPrinter.HighResolution)
        if QPrintDialog(impresora, self).exec():
            imagenes = self._imagenes()
            exportar.documento(self._html(imagenes), imagenes).print_(impresora)
            self.v.accion("imprime el reporte de comparación")
