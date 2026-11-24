"""Proyectos de investigación (A4, D54, RF-D19) y archivado de escenarios (RF-D12).

Un proyecto agrupa escenarios de una enfermedad y una región, con su objetivo, su periodo de estudio y
los motores que contempla. escenarios revisa el dueño, el alcance por región y que el escenario sea de
la misma enfermedad y región; esta pantalla solo arma la petición y muestra lo que responde."""
from html import escape

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSplitter,
                               QVBoxLayout, QWidget)

from .. import api, servicios
from .comun import celda, encabezado, estado, tabla, tarjeta
from .tareas import en_hilo

FILTROS = (("activo", "Activos"), ("archivado", "Archivados"), (None, "Todos"))
COLUMNAS = ("Proyecto", "Enfermedad", "Región", "Periodo", "Motores", "Escenarios", "Estado", "Autor")


class VistaProyectos(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.c = ventana.cliente
        self.lista = []
        self.actual = None
        self.candidatos = []
        self._catalogos = False

        self.filtro = QComboBox()
        for valor, texto in FILTROS:
            self.filtro.addItem(texto, valor)
        self.filtro.currentIndexChanged.connect(self.cargar)
        nuevo = QPushButton("Nuevo proyecto")
        nuevo.setObjectName("primario")
        nuevo.clicked.connect(self.nuevo)
        actualizar = QPushButton("Actualizar")
        actualizar.clicked.connect(self.cargar)
        cabeza, _ = encabezado("Trabajo", "Proyectos de investigación", (self.filtro, actualizar, nuevo))

        divisor = QSplitter()
        divisor.addWidget(self._lista())
        divisor.addWidget(self._panel())
        divisor.setStretchFactor(0, 3)
        divisor.setStretchFactor(1, 2)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(cabeza)
        capa.addWidget(divisor, 1)
        self._mostrar_formulario(None)

    def _lista(self):
        caja = QWidget()
        caja.setObjectName("contenido")
        capa = QVBoxLayout(caja)
        capa.setContentsMargins(16, 16, 8, 16)
        marco, interior = tarjeta("Proyectos de tus regiones")
        self.nota = QLabel("")
        self.nota.setObjectName("nota")
        self.nota.setWordWrap(True)
        self.tabla = tabla(COLUMNAS, estirar=(0,))
        self.tabla.itemSelectionChanged.connect(self._elegir)
        interior.addWidget(self.nota)
        interior.addWidget(self.tabla, 1)
        capa.addWidget(marco, 1)
        return caja

    def _panel(self):
        interior = QWidget()
        interior.setObjectName("contenido")
        capa = QVBoxLayout(interior)
        capa.setContentsMargins(8, 16, 16, 16)

        marco, forma_capa = tarjeta("Proyecto")
        self.titulo = QLabel("")
        self.titulo.setWordWrap(True)
        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("De 3 a 160 caracteres")
        self.objetivo = QPlainTextEdit()
        self.objetivo.setPlaceholderText("Qué se quiere comparar o responder")
        self.objetivo.setFixedHeight(70)
        self.enfermedad = QComboBox()
        self.region = QComboBox()
        self.inicio = QDateEdit(QDate.currentDate())
        self.fin = QDateEdit(QDate.currentDate().addMonths(6))
        for campo in (self.inicio, self.fin):
            campo.setCalendarPopup(True)
            campo.setDisplayFormat("yyyy-MM-dd")
        self.motores = {}
        fila_motores = QHBoxLayout()
        for motor in servicios.MOTORES_PROYECTO:
            casilla = QCheckBox(motor)
            self.motores[motor] = casilla
            fila_motores.addWidget(casilla)
        fila_motores.addStretch(1)
        forma = QFormLayout()
        forma.addRow("Nombre", self.nombre)
        forma.addRow("Objetivo", self.objetivo)
        forma.addRow("Enfermedad", self.enfermedad)
        forma.addRow("Región", self.region)
        forma.addRow("Desde", self.inicio)
        forma.addRow("Hasta", self.fin)
        forma.addRow("Motores", fila_motores)
        self.guardar = QPushButton("Crear proyecto")
        self.guardar.setObjectName("primario")
        self.guardar.clicked.connect(self.guardar_proyecto)
        self.archivar = QPushButton("Archivar proyecto")
        self.archivar.clicked.connect(self.archivar_proyecto)
        botones = QHBoxLayout()
        botones.addWidget(self.archivar)
        botones.addStretch(1)
        botones.addWidget(self.guardar)
        self.mensaje = QLabel("")
        self.mensaje.setWordWrap(True)
        forma_capa.addWidget(self.titulo)
        forma_capa.addLayout(forma)
        forma_capa.addLayout(botones)
        forma_capa.addWidget(self.mensaje)
        # La tarjeta del formulario conserva su alto: sin esto, con la de escenarios oculta (proyecto
        # nuevo), se estiraba a toda la columna y repartía el espacio entre los campos.
        marco.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        capa.addWidget(marco)

        marco_esc, esc = tarjeta("Escenarios del proyecto")
        self.escenarios = tabla(("Escenario", "Versión vigente", "Estado de la versión", "Escenario archivado"),
                                estirar=(0,))
        self.escenarios.itemSelectionChanged.connect(self._habilitar)
        self.b_abrir = QPushButton("Abrir")
        self.b_abrir.clicked.connect(self.abrir_escenario)
        self.b_quitar = QPushButton("Sacar del proyecto")
        self.b_quitar.clicked.connect(self.sacar_escenario)
        self.b_archivar_esc = QPushButton("Archivar escenario")
        self.b_archivar_esc.setToolTip("Queda de solo lectura: sin versiones, envíos ni corridas nuevas (RF-D12).")
        self.b_archivar_esc.clicked.connect(self.archivar_escenario)
        acciones = QHBoxLayout()
        for boton in (self.b_abrir, self.b_quitar, self.b_archivar_esc):
            acciones.addWidget(boton)
        acciones.addStretch(1)
        self.agregar_combo = QComboBox()
        self.b_agregar = QPushButton("Agregar al proyecto")
        self.b_agregar.clicked.connect(self.agregar_escenario)
        fila_agregar = QHBoxLayout()
        fila_agregar.addWidget(self.agregar_combo, 1)
        fila_agregar.addWidget(self.b_agregar)
        self.nota_agregar = QLabel("Solo entran escenarios de la misma enfermedad y región.")
        self.nota_agregar.setObjectName("nota")
        self.nota_agregar.setWordWrap(True)
        esc.addWidget(self.escenarios, 1)
        esc.addLayout(acciones)
        esc.addLayout(fila_agregar)
        esc.addWidget(self.nota_agregar)
        capa.addWidget(marco_esc, 1)
        # Con factor 0 solo crece si la tarjeta de escenarios está oculta: deja el formulario arriba.
        capa.addStretch(0)
        self.marco_escenarios = marco_esc

        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setWidget(interior)
        return desplazable

    # --- carga -----------------------------------------------------------------------------------

    def al_mostrar(self):
        if not self._catalogos:
            en_hilo(_catalogos, self.c, listo=self._poner_catalogos, fallo=self.v.mostrar_error)
        self.cargar()

    def _poner_catalogos(self, datos):
        enfermedades, regiones = datos
        self._catalogos = True
        self.enfermedad.clear()
        for e in enfermedades:
            self.enfermedad.addItem(e.get("nombre") or e.get("code"), e.get("id"))
        self.region.clear()
        for r in regiones:
            self.region.addItem(r.get("nombre"), r.get("id"))
        if self.actual:
            self._poner_combos(self.actual)

    def cargar(self, *_):
        en_hilo(servicios.proyectos, self.c, self.filtro.currentData(), listo=self._poner, fallo=self.v.mostrar_error)

    def _poner(self, proyectos):
        self.lista = proyectos
        elegido = self.actual["id"] if self.actual else None
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        for p in proyectos:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            valores = (p.get("name"), p.get("enfermedad"), p.get("region"),
                       "%s a %s" % (p.get("period_start"), p.get("period_end")), ", ".join(p.get("motores") or []),
                       p.get("n_escenarios"), estado(p.get("status"))[0], p.get("autor"))
            for col, valor in enumerate(valores):
                self.tabla.setItem(fila, col, celda(valor, p.get("status") if col == 6 else None,
                                                    alinear_derecha=col == 5))
            if p.get("id") == elegido:
                self.tabla.selectRow(fila)
        self.tabla.blockSignals(False)
        self.nota.setText("%d proyectos. Un proyecto reúne escenarios de una enfermedad y una región." % len(proyectos)
                          if proyectos else "No hay proyectos con este filtro. Crea uno con «Nuevo proyecto».")

    def _elegir(self):
        fila = self.tabla.currentRow()
        if 0 <= fila < len(self.lista):
            self.abrir(self.lista[fila]["id"])

    def abrir(self, proyecto_id):
        en_hilo(servicios.proyecto, self.c, proyecto_id, listo=self._mostrar_formulario, fallo=self.v.mostrar_error)

    def nuevo(self):
        self.tabla.clearSelection()
        self._mostrar_formulario(None)

    def _mostrar_formulario(self, proyecto):
        self.actual = proyecto
        self.mensaje.setText("")
        self.nombre.setText((proyecto or {}).get("name") or "")
        self.objetivo.setPlainText((proyecto or {}).get("objective") or "")
        motores = set((proyecto or {}).get("motores") or ["seir-ref"])
        for motor, casilla in self.motores.items():
            casilla.setChecked(motor in motores)
        if proyecto is None:
            self.titulo.setText("<b>Nuevo proyecto</b>")
            self.inicio.setDate(QDate.currentDate())
            self.fin.setDate(QDate.currentDate().addMonths(6))
            self.guardar.setText("Crear proyecto")
            self.escenarios.setRowCount(0)
        else:
            self.titulo.setText("<b>%s</b> · %s · de %s" % (escape(proyecto.get("name") or ""),
                                                           escape(estado(proyecto.get("status"))[0]),
                                                           escape(proyecto.get("autor") or "—")))
            self.inicio.setDate(QDate.fromString(proyecto.get("period_start") or "", "yyyy-MM-dd"))
            self.fin.setDate(QDate.fromString(proyecto.get("period_end") or "", "yyyy-MM-dd"))
            self.guardar.setText("Guardar cambios")
            self.archivar.setText("Restaurar proyecto" if proyecto.get("status") == "archivado"
                                  else "Archivar proyecto")
            self._poner_combos(proyecto)
            self._poner_escenarios(proyecto.get("escenarios") or [])
            self._buscar_candidatos()
        self._habilitar()

    def _poner_combos(self, proyecto):
        for combo, clave in ((self.enfermedad, "disease_id"), (self.region, "region_id")):
            indice = combo.findData(proyecto.get(clave))
            if indice >= 0:
                combo.setCurrentIndex(indice)

    def _poner_escenarios(self, escenarios):
        self.escenarios.setRowCount(len(escenarios))
        for fila, e in enumerate(escenarios):
            self.escenarios.setItem(fila, 0, celda(e.get("name"), dato=e))
            self.escenarios.setItem(fila, 1, celda("v%s" % e.get("version_number")))
            self.escenarios.setItem(fila, 2, celda(estado(e.get("version_status"))[0], e.get("version_status")))
            self.escenarios.setItem(fila, 3, celda("Sí" if e.get("status") == "archivado" else "No"))

    def _buscar_candidatos(self):
        self.agregar_combo.clear()
        self.candidatos = []
        en_hilo(servicios.escenarios, self.c, listo=self._poner_candidatos, fallo=self.v.mostrar_error)

    def _poner_candidatos(self, escenarios):
        p = self.actual
        if not p:
            return
        self.candidatos = [e for e in escenarios if e.get("project_id") != p["id"]
                           and e.get("enfermedad") == p.get("enfermedad") and e.get("region") == p.get("region")]
        self.agregar_combo.clear()
        for e in self.candidatos:
            otro = " (está en otro proyecto)" if e.get("project_id") else ""
            self.agregar_combo.addItem("%s · v%s%s" % (e.get("name"), e.get("version_number"), otro), e.get("id"))
        self.nota_agregar.setText("Solo entran escenarios de %s en %s." % (p.get("enfermedad"), p.get("region"))
                                  if self.candidatos else
                                  "No hay otros escenarios de %s en %s." % (p.get("enfermedad"), p.get("region")))
        self._habilitar()

    # --- permisos en pantalla (el servidor decide) -------------------------------------------------

    def puede_cambiar(self):
        if not self.actual:
            return True
        return self.v.es_admin() or self.actual.get("owner_id") == (self.c.usuario or {}).get("id")

    def _escenario_elegido(self):
        fila = self.escenarios.currentRow()
        item = self.escenarios.item(fila, 0) if fila >= 0 else None
        return item.data(Qt.UserRole) if item else None

    def _habilitar(self):
        p = self.actual
        activo = p is None or p.get("status") == "activo"
        dueno = self.puede_cambiar()
        for campo in (self.nombre, self.objetivo, self.inicio, self.fin, *self.motores.values()):
            campo.setEnabled(activo and dueno)
        con_escenarios = bool(p and (p.get("n_escenarios") or p.get("escenarios")))
        self.enfermedad.setEnabled(activo and dueno and not con_escenarios)
        self.region.setEnabled(activo and dueno and not con_escenarios)
        self.guardar.setEnabled(activo and dueno)
        self.archivar.setVisible(p is not None)
        self.archivar.setEnabled(p is not None and dueno)
        self.marco_escenarios.setVisible(p is not None)
        elegido = self._escenario_elegido()
        self.b_abrir.setEnabled(elegido is not None)
        self.b_quitar.setEnabled(elegido is not None and activo)
        self.b_archivar_esc.setEnabled(elegido is not None)
        if elegido is not None:
            self.b_archivar_esc.setText("Restaurar escenario" if elegido.get("status") == "archivado"
                                        else "Archivar escenario")
        self.b_agregar.setEnabled(activo and bool(self.candidatos))
        self.agregar_combo.setEnabled(activo and bool(self.candidatos))

    # --- acciones --------------------------------------------------------------------------------

    def datos_formulario(self):
        return {"name": self.nombre.text().strip(), "objective": self.objetivo.toPlainText().strip() or None,
                "disease_id": self.enfermedad.currentData(), "region_id": self.region.currentData(),
                "period_start": self.inicio.date().toString("yyyy-MM-dd"),
                "period_end": self.fin.date().toString("yyyy-MM-dd"),
                "motores": [m for m, casilla in self.motores.items() if casilla.isChecked()]}

    def guardar_proyecto(self):
        datos = self.datos_formulario()
        if len(datos["name"]) < 3:
            self.mensaje.setText("El nombre necesita al menos 3 caracteres.")
            return
        if not datos["motores"]:
            self.mensaje.setText("Elige al menos un motor.")
            return
        if datos["disease_id"] is None or datos["region_id"] is None:
            self.mensaje.setText("Elige la enfermedad y la región.")
            return
        if datos["period_end"] < datos["period_start"]:
            self.mensaje.setText("El periodo termina antes de empezar.")
            return
        self.guardar.setEnabled(False)
        if self.actual is None:
            en_hilo(servicios.crear_proyecto, self.c, datos, listo=self._guardado, fallo=self._fallo)
            return
        cambios = {k: v for k, v in datos.items() if v != self.actual.get(k)}
        if not cambios:
            self.mensaje.setText("No hay cambios que guardar.")
            self._habilitar()
            return
        en_hilo(servicios.cambiar_proyecto, self.c, self.actual["id"], cambios, listo=self._guardado,
                fallo=self._fallo)

    def _guardado(self, proyecto):
        self.v.accion("guardó el proyecto %s" % proyecto.get("id"))
        self.actual = proyecto
        self.cargar()
        self.abrir(proyecto["id"])

    def archivar_proyecto(self):
        p = self.actual
        if not p:
            return
        archivar = p.get("status") != "archivado"
        if archivar and QMessageBox.question(
                self, "Archivar", "«%s» dejará de recibir escenarios y cambios. Sus escenarios no cambian. "
                "¿Archivarlo?" % p.get("name")) != QMessageBox.Yes:
            return
        en_hilo(servicios.archivar_proyecto, self.c, p["id"], archivar, listo=self._guardado, fallo=self._fallo)

    def agregar_escenario(self):
        escenario_id = self.agregar_combo.currentData()
        if self.actual and escenario_id:
            en_hilo(servicios.mover_a_proyecto, self.c, escenario_id, self.actual["id"],
                    listo=self._escenario_movido, fallo=self._fallo)

    def sacar_escenario(self):
        e = self._escenario_elegido()
        if e:
            en_hilo(servicios.mover_a_proyecto, self.c, e["id"], None, listo=self._escenario_movido, fallo=self._fallo)

    def _escenario_movido(self, datos):
        self.v.accion("movió el escenario %s al proyecto %s" % (datos.get("scenario_id"), datos.get("project_id")))
        self._recargar_actual()

    def archivar_escenario(self):
        e = self._escenario_elegido()
        if not e:
            return
        archivar = e.get("status") != "archivado"
        if archivar and QMessageBox.question(
                self, "Archivar", "«%s» quedará de solo lectura: sin versiones, envíos a revisión ni corridas "
                "nuevas. Sus corridas y resultados se siguen consultando. ¿Archivarlo?" % e.get("name")) \
                != QMessageBox.Yes:
            return
        en_hilo(servicios.archivar_escenario, self.c, e["id"], archivar, listo=self._escenario_archivado,
                fallo=self._fallo)

    def _escenario_archivado(self, datos):
        self.v.accion("cambió el escenario %s a %s" % (datos.get("id"), datos.get("status")))
        self._recargar_actual()

    def _recargar_actual(self):
        self.cargar()
        if self.actual:
            self.abrir(self.actual["id"])

    def abrir_escenario(self):
        e = self._escenario_elegido()
        if e:
            self.v.abrir_escenario(e["id"], None)

    def _fallo(self, exc):
        self._habilitar()
        if isinstance(exc, api.ErrorServicio) and exc.status in (400, 409, 422):
            detalle = "\n".join("• " + (x.get("mensaje") if isinstance(x, dict) else str(x))
                                for x in (exc.errores or [])[:10])
            self.mensaje.setText("%s%s" % (exc, ("\n" + detalle) if detalle else ""))
            return
        self.v.mostrar_error(exc)


def _catalogos(c):
    return servicios.enfermedades(c), servicios.regiones(c)
