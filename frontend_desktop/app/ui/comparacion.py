from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from .. import exportar, resumen, servicios
from . import graficas
from .comun import celda, encabezado, limpiar, num, pct, tabla, tarjeta
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

        self.b_csv = QPushButton("Exportar CSV")
        self.b_pdf = QPushButton("Exportar PDF")
        self.b_imprimir = QPushButton("Imprimir")
        self.b_imprimir.setObjectName("primario")
        self.b_csv.clicked.connect(self.exportar_csv)
        self.b_pdf.clicked.connect(self.exportar_pdf)
        self.b_imprimir.clicked.connect(self.imprimir)
        cabeza, _ = encabezado("Trabajo", "Comparación de escenarios", (self.b_csv, self.b_pdf, self.b_imprimir))

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
        capa = QVBoxLayout(contenido)
        capa.setContentsMargins(16, 16, 16, 16)

        marco, interior = tarjeta()
        fichas = QWidget()
        self.capa_fichas = QHBoxLayout(fichas)
        self.capa_fichas.setContentsMargins(0, 0, 0, 0)
        desplazar = QScrollArea()
        desplazar.setWidgetResizable(True)
        desplazar.setFrameShape(QFrame.NoFrame)
        desplazar.setFixedHeight(48)
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
        capa.addWidget(marco)

        graficas_fila = QHBoxLayout()
        izquierda, capa_izq = tarjeta("Frontera de eficiencia")
        nota = QLabel("Menor es mejor en ambos ejes. Punto: mediana; barra: p5–p95. "
                      "Frontera sobre medianas (D8, propuesta).")
        nota.setObjectName("nota")
        nota.setWordWrap(True)
        self.g_frontera = graficas.vista()
        capa_izq.addWidget(nota)
        capa_izq.addWidget(self.g_frontera)
        derecha, capa_der = tarjeta("Casos activos superpuestos")
        nota = QLabel("Mediana de cada escenario; banda p5–p95 del seleccionado en la tabla.")
        nota.setObjectName("nota")
        nota.setWordWrap(True)
        self.g_curvas = graficas.vista()
        capa_der.addWidget(nota)
        capa_der.addWidget(self.g_curvas)
        graficas_fila.addWidget(izquierda)
        graficas_fila.addWidget(derecha)
        capa.addLayout(graficas_fila)

        indicadores, capa_ind = tarjeta("Indicadores por escenario")
        self.nota_tabla = QLabel()
        self.nota_tabla.setObjectName("nota")
        self.tabla = tabla(["Escenario", "Réplicas", "Muertes", "Pico de casos activos", "Día del pico",
                            "Tasa de ataque", "Costo", "Frontera"], estirar=(0, 7))
        self.tabla.setMinimumHeight(180)
        self.tabla.itemSelectionChanged.connect(self._elegir)
        capa_ind.addWidget(self.nota_tabla)
        capa_ind.addWidget(self.tabla)
        capa.addWidget(indicadores)

        self.aviso = QLabel("Agrega al menos dos versiones con corridas completadas y pulsa Comparar.")
        self.aviso.setObjectName("aviso")
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
        self.lectura.setWordWrap(True)
        seleccionado = QLabel("Seleccionado")
        seleccionado.setObjectName("tituloTarjeta")
        self.detalle = QLabel("—")
        self.detalle.setWordWrap(True)
        self.detalle.setTextFormat(Qt.RichText)
        pie = QLabel("Elegir entre los escenarios de la frontera es una decisión humana; este análisis no "
                     "recomienda ninguno ni constituye asesoría sanitaria.")
        pie.setObjectName("nota")
        pie.setWordWrap(True)
        capa.addWidget(titulo)
        capa.addWidget(self.lectura)
        capa.addSpacing(12)
        capa.addWidget(seleccionado)
        capa.addWidget(self.detalle)
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
        self.b_comparar.setEnabled(len(self.elegidas) >= 2)
        for b in (self.b_csv, self.b_pdf, self.b_imprimir):
            b.setEnabled(self.datos is not None)

    def comparar(self):
        self.b_comparar.setEnabled(False)
        self.b_comparar.setText("Comparando…")
        ids = [e["version_id"] for e in self.elegidas]
        self.v.accion("compara las versiones %s" % ids)
        en_hilo(servicios.cargar_comparacion, self.c, ids, self.metrica.currentData(),
                listo=self._mostrar, fallo=self._fallo)

    def _fallo(self, exc):
        self.b_comparar.setText("Comparar")
        self._habilitar()
        self.v.mostrar_error(exc)

    def _mostrar(self, datos):
        self.datos = datos
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
                       exportar.texto_frontera(e))
            for col, valor in enumerate(valores):
                clave = None
                if col == 7:
                    clave = "aprobado" if e["dominado_por"] == [] else "borrador"
                self.tabla.setItem(fila, col, celda(valor, clave))
        self.tabla.blockSignals(False)
        self.tabla.selectRow(0)
        supuestos = "Modelo de costo: %s." % (datos.get("modelo_costo") or "—")
        sin_fuente = [c["tipo"] for c in datos["trazabilidad_costos"] if c.get("estado") != "con_fuente"]
        if sin_fuente:
            supuestos += " Costos sin fuente o marcados como supuesto: %s." % ", ".join(sin_fuente)
        for aviso in datos["avisos"]:
            supuestos += " " + aviso
        self.aviso.setText("%s\n\nSupuestos: %s" % (datos["aviso"], supuestos))
        self._lectura()
        self._pintar()

    def _lectura(self):
        escenarios = self.datos["escenarios"]
        if all(e["costo"] is None for e in escenarios):
            self.lectura.setText("No hay frontera: el servicio pareto no calculó costos.\n\n"
                                 + "\n".join("• " + a for a in self.datos["avisos"]))
            return
        frente = [e["nombre"] for e in escenarios if e["dominado_por"] == []]
        lineas = ["%d de %d escenarios están en la frontera: %s." % (len(frente), len(escenarios), ", ".join(frente))]
        for e in escenarios:
            if e["dominado_por"]:
                lineas.append("%s tiene igual o más %s con igual o más costo que %s." % (
                    e["nombre"], dict(resumen.METRICAS)[self.datos["metrica"]].lower(),
                    ", ".join(e["dominado_por"])))
            elif e["dominado_por"] is None:
                lineas.append("%s no tiene costo calculado y queda fuera de la frontera." % e["nombre"])
        self.lectura.setText("\n\n".join(lineas))

    def _pintar(self):
        escenarios = self.datos["escenarios"]
        nombre = dict(resumen.METRICAS)[self.datos["metrica"]]
        graficas.frontera(self.g_frontera, escenarios, nombre)
        graficas.curvas(self.g_curvas, escenarios, self.seleccion)
        e = escenarios[self.seleccion]
        ind = e["indicadores"]
        filas = [("Réplicas", e["n"]),
                 ("Muertes (media)", num(ind["fallecimientos"]["media"]) if ind["fallecimientos"] else "—"),
                 ("Muertes", _rango(ind["fallecimientos"])),
                 ("Pico de casos activos", _rango(ind["pico_casos_activos"])),
                 ("Día del pico", _rango(ind["dia_pico"])),
                 ("Tasa de ataque", _rango(ind["tasa_ataque"], 1, True)),
                 ("Costo (mediana)", num(e["costo"])),
                 ("Frontera", exportar.texto_frontera(e))]
        self.detalle.setText("<b>%s</b><br>%s" % (e["nombre"], "<br>".join(
            '<span style="color:#64748B">%s:</span> %s' % fila for fila in filas)))

    def _elegir(self):
        fila = self.tabla.currentRow()
        if self.datos and 0 <= fila < len(self.datos["escenarios"]) and fila != self.seleccion:
            self.seleccion = fila
            self._pintar()

    def _imagenes(self):
        return {"frontera.png": self.g_frontera.grab().toImage(), "curvas.png": self.g_curvas.grab().toImage()}

    def _html(self, imagenes):
        usuario = (self.c.usuario or {}).get("full_name") or self.c.nombre_usuario()
        return exportar.reporte_html(self.datos, usuario, list(imagenes))

    def exportar_csv(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "comparacion.csv", "CSV (*.csv)")
        if ruta:
            tabla_ruta, curvas = exportar.csv_comparacion(ruta, self.datos)
            self.v.accion("exporta la comparación a %s" % tabla_ruta)
            QMessageBox.information(self, "Exportar", "Se guardaron:\n%s\n%s" % (tabla_ruta, curvas))

    def exportar_pdf(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar PDF", "comparacion.pdf", "PDF (*.pdf)")
        if ruta:
            imagenes = self._imagenes()
            exportar.guardar_pdf(ruta, self._html(imagenes), imagenes)
            self.v.accion("exporta el reporte de comparación a %s" % ruta)
            QMessageBox.information(self, "Exportar", "Reporte guardado en %s." % ruta)

    def imprimir(self):
        impresora = QPrinter(QPrinter.HighResolution)
        if QPrintDialog(impresora, self).exec():
            imagenes = self._imagenes()
            exportar.documento(self._html(imagenes), imagenes).print_(impresora)
            self.v.accion("imprime el reporte de comparación")
