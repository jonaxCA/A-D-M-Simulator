"""Gestión de datos (A4, D6, D53): importar series observadas, verificar su calidad y ver sus versiones.

El servidor (importacion) revisa, versiona y guarda; esta pantalla solo arma la petición y muestra lo que
responde. La serie es la que usa la calibración (D50)."""
from html import escape

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDateEdit, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSplitter, QVBoxLayout, QWidget)

from .. import api, servicios
from .comun import celda, encabezado, fecha, num, tabla, tarjeta
from .tareas import en_hilo

METRICAS = (("casos_confirmados", "Casos confirmados"), ("hospitalizaciones", "Hospitalizaciones"),
            ("defunciones", "Defunciones"))
PERIODOS = (("semana", "Semana"), ("dia", "Día"))
ESTADO_NL = ("19", "Nuevo León (estado)")
COLUMNAS = ("Clave", "Versión", "Nombre", "Enfermedad", "Región", "Métrica", "Periodo", "Puntos", "Del", "Al",
            "Total", "Importado")


class VistaDatos(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.c = ventana.cliente
        self.archivo = None
        self.lista = []
        self._catalogos = False
        self._ocupado = False

        actualizar = QPushButton("Actualizar")
        actualizar.clicked.connect(self.cargar)
        cabeza, _ = encabezado("Trabajo", "Gestión de datos observados", (actualizar,))

        divisor = QSplitter()
        divisor.addWidget(self._conjuntos())
        divisor.addWidget(self._importar())
        divisor.setStretchFactor(0, 3)
        divisor.setStretchFactor(1, 2)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(cabeza)
        capa.addWidget(divisor, 1)

    def _conjuntos(self):
        caja = QWidget()
        caja.setObjectName("contenido")
        capa = QVBoxLayout(caja)
        capa.setContentsMargins(16, 16, 8, 16)
        marco, interior = tarjeta("Conjuntos importados y sus versiones")
        self.nota = QLabel("Cada clave guarda sus versiones; la más nueva va primero.")
        self.nota.setObjectName("nota")
        self.nota.setWordWrap(True)
        self.tabla = tabla(COLUMNAS, estirar=(2,))
        self.tabla.itemSelectionChanged.connect(self._elegir)
        interior.addWidget(self.nota)
        interior.addWidget(self.tabla, 1)
        capa.addWidget(marco, 3)

        marco_det, det = tarjeta("Serie del conjunto")
        self.detalle = QLabel("Elige un conjunto para ver su fuente, su licencia y sus puntos.")
        self.detalle.setWordWrap(True)
        self.puntos = tabla(("Inicio del periodo", "Valor"), estirar=(0,))
        det.addWidget(self.detalle)
        det.addWidget(self.puntos, 1)
        capa.addWidget(marco_det, 2)
        return caja

    def _importar(self):
        caja = QWidget()
        caja.setObjectName("contenido")
        capa = QVBoxLayout(caja)
        capa.setContentsMargins(8, 16, 16, 16)
        marco, interior = tarjeta("Importar una serie")
        ayuda = QLabel("CSV, JSON o XML de hasta 2 MB con periodo_inicio y valor (entero no negativo), periodos "
                       "seguidos y sin repetir. Primero verifica la calidad; importar crea la versión siguiente.")
        ayuda.setObjectName("nota")
        ayuda.setWordWrap(True)
        interior.addWidget(ayuda)

        self.ruta = QLabel("Ningún archivo elegido")
        self.ruta.setWordWrap(True)
        elegir = QPushButton("Elegir archivo…")
        elegir.clicked.connect(self.elegir_archivo)
        fila = QHBoxLayout()
        fila.addWidget(self.ruta, 1)
        fila.addWidget(elegir)
        interior.addLayout(fila)

        self.campos = {}
        forma = QFormLayout()
        for clave, etiqueta, ayuda_campo in (("code", "Clave", "MAYÚSCULAS, dígitos y _ (por ejemplo COVID19_NL_2020)"),
                                            ("name", "Nombre", "Qué mide la serie y de cuándo"),
                                            ("source", "Fuente", "Institución y publicación de donde salió"),
                                            ("license", "Licencia", "Con qué licencia se puede usar"),
                                            ("url", "URL de la fuente", "Opcional")):
            campo = QLineEdit()
            campo.setPlaceholderText(ayuda_campo)
            self.campos[clave] = campo
            forma.addRow(etiqueta, campo)
        self.enfermedad = QComboBox()
        self.region = QComboBox()
        self.metrica = QComboBox()
        for valor, texto in METRICAS:
            self.metrica.addItem(texto, valor)
        self.periodo = QComboBox()
        for valor, texto in PERIODOS:
            self.periodo.addItem(texto, valor)
        self.corte = QDateEdit(QDate.currentDate())
        self.corte.setCalendarPopup(True)
        self.corte.setDisplayFormat("yyyy-MM-dd")
        forma.insertRow(2, "Enfermedad", self.enfermedad)
        forma.insertRow(3, "Región", self.region)
        forma.insertRow(4, "Métrica", self.metrica)
        forma.insertRow(5, "Periodo", self.periodo)
        forma.addRow("Fecha de corte", self.corte)
        interior.addLayout(forma)

        self.b_verificar = QPushButton("Verificar calidad")
        self.b_verificar.clicked.connect(self.verificar)
        self.b_importar = QPushButton("Importar")
        self.b_importar.setObjectName("primario")
        self.b_importar.clicked.connect(self.importar)
        botones = QHBoxLayout()
        botones.addStretch(1)
        botones.addWidget(self.b_verificar)
        botones.addWidget(self.b_importar)
        interior.addLayout(botones)

        self.resultado = QLabel("")
        self.resultado.setWordWrap(True)
        interior.addWidget(self.resultado)
        interior.addStretch(1)
        capa.addWidget(marco, 1)
        self._habilitar()
        return caja

    def al_mostrar(self):
        if not self._catalogos:
            en_hilo(_catalogos, self.c, listo=self._poner_catalogos, fallo=self.v.mostrar_error)
        self.cargar()

    def _poner_catalogos(self, datos):
        enfermedades, regiones = datos
        self._catalogos = True
        self.enfermedad.clear()
        for e in enfermedades:
            self.enfermedad.addItem("%s · %s" % (e.get("code"), e.get("nombre")), e.get("code"))
        self.region.clear()
        self.region.addItem("%s · %s" % ESTADO_NL, ESTADO_NL[0])
        for m in regiones:
            self.region.addItem("%s · %s" % (m.get("code"), m.get("nombre")), m.get("code"))

    def cargar(self):
        en_hilo(servicios.conjuntos, self.c, listo=self._poner, fallo=self.v.mostrar_error)

    def _poner(self, conjuntos):
        self.lista = conjuntos
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        for conjunto in conjuntos:
            resumen = conjunto.get("resumen") or {}
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            valores = (conjunto.get("code"), conjunto.get("version"), conjunto.get("name"), conjunto.get("disease"),
                       conjunto.get("region"), dict(METRICAS).get(conjunto.get("metric"), conjunto.get("metric")),
                       dict(PERIODOS).get(conjunto.get("period"), conjunto.get("period")),
                       resumen.get("puntos"), resumen.get("inicio"), resumen.get("fin"), num(resumen.get("total")),
                       fecha(conjunto.get("created_at")))
            for col, valor in enumerate(valores):
                self.tabla.setItem(fila, col, celda(valor, alinear_derecha=col in (1, 7, 10)))
        self.tabla.blockSignals(False)
        self.nota.setText("%d versiones. Cada clave guarda sus versiones; la más nueva va primero." % len(conjuntos)
                          if conjuntos else "Aún no hay conjuntos importados en tus regiones.")

    def _elegir(self):
        fila = self.tabla.currentRow()
        if not 0 <= fila < len(self.lista):
            return
        conjunto = self.lista[fila]
        resumen = conjunto.get("resumen") or {}
        self.detalle.setText(
            "<b>%s v%s</b><br>Fuente: %s<br>Licencia: %s<br>Corte: %s · huella %s…<br>"
            "%s periodos en cero · máximo %s" % (
                _html(conjunto.get("code")), conjunto.get("version"), _html(conjunto.get("source")),
                _html(conjunto.get("license")), _html(conjunto.get("cutoff_date")),
                _html((conjunto.get("sha256") or "")[:12]), resumen.get("periodos_en_cero", "—"),
                num(resumen.get("maximo"))))
        en_hilo(servicios.puntos_conjunto, self.c, conjunto["id"], listo=self._poner_puntos, fallo=self.v.mostrar_error)

    def _poner_puntos(self, puntos):
        self.puntos.setRowCount(len(puntos))
        for fila, punto in enumerate(puntos):
            self.puntos.setItem(fila, 0, celda(punto.get("periodo_inicio")))
            self.puntos.setItem(fila, 1, celda(num(punto.get("valor")), alinear_derecha=True))

    def elegir_archivo(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir serie", "", "Series (*.csv *.json *.xml)")
        if ruta:
            self.usar_archivo(ruta)

    def usar_archivo(self, ruta):
        try:
            self.archivo = servicios.leer_conjunto(ruta)
        except (OSError, api.ErrorServicio) as exc:
            self.archivo = None
            self.resultado.setText(str(exc) if isinstance(exc, api.ErrorServicio) else "No se pudo leer el archivo.")
        else:
            self.ruta.setText(str(ruta))
            self.resultado.setText("")
        self._habilitar()

    def metadatos(self):
        datos = {clave: campo.text() for clave, campo in self.campos.items()}
        datos.update(disease=self.enfermedad.currentData() or "", region=self.region.currentData() or "",
                     metric=self.metrica.currentData(), period=self.periodo.currentData(),
                     cutoff=self.corte.date().toString("yyyy-MM-dd"))
        return datos

    def _habilitar(self):
        listo = self.archivo is not None and not self._ocupado
        self.b_verificar.setEnabled(listo)
        self.b_importar.setEnabled(listo)

    def _empezar(self, texto):
        self._ocupado = True
        self._habilitar()
        self.resultado.setText(texto)

    def verificar(self):
        if self.archivo is None or self._ocupado:
            return
        self._empezar("Verificando…")
        contenido, tipo = self.archivo
        en_hilo(servicios.validar_conjunto, self.c, contenido, tipo, self.metadatos(),
                listo=self._verificado, fallo=self._fallo)

    def _verificado(self, datos):
        self._ocupado = False
        self._habilitar()
        if datos.get("valido"):
            r = datos.get("resumen") or {}
            self.resultado.setText("La serie pasa la revisión: %s puntos del %s al %s, total %s, máximo %s, %s "
                                   "periodos en cero. Ya se puede importar." % (
                                       r.get("puntos"), r.get("inicio"), r.get("fin"), num(r.get("total")),
                                       num(r.get("maximo")), r.get("periodos_en_cero")))
        else:
            fallas = datos.get("fallas") or []
            self.resultado.setText("La serie no pasa la revisión (%d fallas):\n%s"
                                   % (len(fallas), "\n".join("• " + f for f in fallas)))

    def importar(self):
        if self.archivo is None or self._ocupado:
            return
        self._empezar("Importando…")
        contenido, tipo = self.archivo
        en_hilo(servicios.importar_conjunto, self.c, contenido, tipo, self.metadatos(),
                listo=self._importado, fallo=self._fallo)

    def _importado(self, conjunto):
        self._ocupado = False
        self._habilitar()
        self.v.accion("importó el conjunto %s v%s" % (conjunto.get("code"), conjunto.get("version")))
        if conjunto.get("ya_existia"):
            texto = "Ese archivo ya estaba importado con esa clave: es %s v%s. No se creó otra versión."
        else:
            texto = "Se importó %s v%s."
        self.resultado.setText(texto % (conjunto.get("code"), conjunto.get("version")))
        self.cargar()

    def _fallo(self, exc):
        self._ocupado = False
        self._habilitar()
        errores = getattr(exc, "errores", None) or []
        if isinstance(exc, api.ErrorServicio) and exc.status in (400, 413, 415, 422):
            detalle = "\n".join("• " + (e.get("mensaje") if isinstance(e, dict) else str(e)) for e in errores[:50])
            self.resultado.setText("El servidor rechazó la serie: %s%s" % (exc, ("\n" + detalle) if detalle else ""))
            return
        self.resultado.setText("")
        self.v.mostrar_error(exc)


def _catalogos(c):
    return servicios.enfermedades(c), servicios.regiones(c)


def _html(texto):
    return escape(str(texto)) if texto not in (None, "") else "—"
