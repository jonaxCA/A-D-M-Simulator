from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from .. import api, servicios
from . import graficas
from .comun import celda, num, tabla
from .mapa import MapaMunicipal, NIVELES
from .tareas import en_hilo


class DialogoZonas(QDialog):
    def __init__(self, padre, ventana, enfermedad_id, enfermedad):
        super().__init__(padre)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Indicadores municipales · %s" % enfermedad)
        self.resize(1050, 650)
        self.ventana = ventana
        self.enfermedad_id = enfermedad_id
        self.fechas = []
        self.serie_municipal = {}
        self.geometria = None
        self.etag = None
        self.indicadores = []
        self.filas_por_codigo = {}

        capa = QVBoxLayout(self)
        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Periodo"))
        self.periodo = QComboBox()
        for dias in (7, 30, 60):
            self.periodo.addItem("%d días" % dias, dias)
        self.periodo.currentIndexChanged.connect(self.cargar)
        filtros.addWidget(self.periodo)
        filtros.addStretch(1)
        capa.addLayout(filtros)
        self.fuente = QLabel()
        self.fuente.setWordWrap(True)
        self.fuente.setTextFormat(Qt.PlainText)
        capa.addWidget(self.fuente)
        self.leyenda = QLabel(" · ".join('<span style="color:%s">■</span> %s' % (color, nombre)
                                         for nombre, color in NIVELES.values()))
        self.leyenda.setTextFormat(Qt.RichText)
        self.leyenda.setWordWrap(True)
        self.leyenda.hide()
        capa.addWidget(self.leyenda)
        contenido = QHBoxLayout()
        self.graficos = QStackedWidget()
        self.mapa = graficas.vista()
        self.poligonos = MapaMunicipal()
        self.poligonos.municipio.connect(self._elegir_municipio)
        self.graficos.addWidget(self.mapa)
        self.graficos.addWidget(self.poligonos)
        contenido.addWidget(self.graficos, 1)
        self.tabla = tabla(["Municipio", "Casos", "Incidencia por 100 000", "Nivel"], estirar=(0,))
        self.tabla.currentCellChanged.connect(self._mostrar_serie)
        pestanas = QTabWidget()
        pestanas.addTab(self.tabla, "Municipios")
        consulta = QWidget()
        capa_serie = QVBoxLayout(consulta)
        self.encabezado_serie = QLabel("Elige un municipio en la tabla.")
        self.encabezado_serie.setTextFormat(Qt.PlainText)
        self.encabezado_serie.setWordWrap(True)
        capa_serie.addWidget(self.encabezado_serie)
        self.tabla_serie = tabla(["Fecha", "Casos acumulados", "Incidencia por 100 000"], estirar=(0,))
        capa_serie.addWidget(self.tabla_serie)
        pestanas.addTab(consulta, "Serie registrada")
        contenido.addWidget(pestanas, 1)
        capa.addLayout(contenido, 1)
        botones = QDialogButtonBox(QDialogButtonBox.Close)
        botones.button(QDialogButtonBox.Close).setText("Cerrar")
        botones.rejected.connect(self.reject)
        capa.addWidget(botones)
        self.cargar()

    def cargar(self):
        self.periodo.setEnabled(False)
        self.fuente.setText("Consultando indicadores municipales del servicio zonas…")
        self.tabla.setRowCount(0)
        self.tabla_serie.setRowCount(0)
        self.graficos.setCurrentWidget(self.mapa)
        self.leyenda.hide()
        graficas.sin_datos(self.mapa, "Consultando coordenadas…")
        en_hilo(servicios.zonas_mapa, self.ventana.cliente, self.enfermedad_id, self.periodo.currentData(),
                listo=self._mostrar, fallo=self._fallo)

    def _mostrar(self, datos):
        municipios = datos.get("municipios") or []
        self.indicadores = municipios
        self.filas_por_codigo = {}
        serie = datos.get("serie") or {}
        self.fechas = serie.get("fechas") or []
        self.serie_municipal = {s["region_code"]: s for s in serie.get("municipios") or []}
        periodo = datos.get("filtros", {}).get("days") or self.periodo.currentData()
        intervalo = " · %s a %s" % (self.fechas[0], self.fechas[-1]) if self.fechas else ""
        self.periodo_texto = "Fuente de incidencia: zonas · periodo de %s días%s." % (periodo, intervalo)
        self.fuente.setText(self.periodo_texto + " Consultando límites municipales…")
        for municipio in municipios:
            fila = self.tabla.rowCount()
            self.filas_por_codigo[municipio["region_code"]] = fila
            self.tabla.insertRow(fila)
            valores = (municipio["nombre"], num(municipio.get("casos")), num(municipio.get("incidencia"), 2),
                       municipio.get("nivel"))
            for col, valor in enumerate(valores):
                self.tabla.setItem(fila, col, celda(valor, dato=municipio.get("region_code") if col == 0 else None))
        graficas.municipios(self.mapa, municipios)
        if municipios:
            self.tabla.selectRow(0)
        en_hilo(servicios.geometria_municipal, self.ventana.cliente, self.etag,
                listo=self._mostrar_geometria, fallo=self._fallo_geometria)

    def _mostrar_geometria(self, resultado):
        datos, self.etag = resultado
        if datos is not None:
            self.geometria = datos
        self.periodo.setEnabled(True)
        if not self.geometria or not self.geometria.get("features"):
            self.fuente.setText(self.periodo_texto + " Geometría sin municipios. Se muestran coordenadas.")
            return
        self.graficos.setCurrentWidget(self.poligonos)
        self.poligonos.poner(self.geometria, self.indicadores)
        item = self.tabla.item(self.tabla.currentRow(), 0)
        self.poligonos.elegir(item.data(Qt.UserRole) if item else None)
        fuente = self.geometria.get("fuente") or {}
        self.fuente.setText(self.periodo_texto + " Límites: " + (fuente.get("documento") or "servicio zonas") + ".")
        self.leyenda.show()

    def _fallo_geometria(self, exc):
        self.periodo.setEnabled(True)
        self.fuente.setText(self.periodo_texto + " Límites no disponibles. Se muestran coordenadas.")
        if isinstance(exc, api.SesionCerrada):
            self.ventana.mostrar_error(exc)

    def _elegir_municipio(self, codigo):
        if codigo in self.filas_por_codigo:
            self.tabla.selectRow(self.filas_por_codigo[codigo])

    def _mostrar_serie(self, fila, *_):
        self.tabla_serie.setRowCount(0)
        municipio = self.tabla.item(fila, 0)
        self.poligonos.elegir(municipio.data(Qt.UserRole) if municipio is not None else None)
        if municipio is None:
            self.encabezado_serie.setText("Elige un municipio en la tabla.")
            return
        serie = self.serie_municipal.get(municipio.data(Qt.UserRole))
        if not serie or not self.fechas:
            self.encabezado_serie.setText("El servicio no devolvió una serie para %s." % municipio.text())
            return
        self.encabezado_serie.setText("%s · casos acumulados según el periodo del servicio zonas." % municipio.text())
        self.tabla_serie.setRowCount(len(self.fechas))
        casos = serie.get("casos") or []
        incidencia = serie.get("incidencia") or []
        for i, dia in enumerate(self.fechas):
            valores = (dia, num(casos[i]) if i < len(casos) else "—",
                       num(incidencia[i], 2) if i < len(incidencia) else "—")
            for col, valor in enumerate(valores):
                self.tabla_serie.setItem(i, col, celda(valor))

    def _fallo(self, exc):
        self.periodo.setEnabled(True)
        self.fuente.setText("El servicio no devolvió indicadores para este periodo.")
        graficas.sin_datos(self.mapa, "Indicadores no disponibles")
        self.ventana.mostrar_error(exc)
