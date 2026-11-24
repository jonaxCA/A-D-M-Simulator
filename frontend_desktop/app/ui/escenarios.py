from html import escape
from pathlib import Path
from defusedxml import ElementTree as XMLSeguro
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget)

from .. import api, esquemas, servicios
from .ajustes import DialogoAjustes
from .auditoria import DialogoAuditoria
from .comun import celda, dato_vertical, encabezado, estado, fecha, num, tabla, tarjeta
from .formularios import DialogoEscenario, DialogoVersion, FormIntervencion, mostrar_parametros
from .linea_tiempo import LineaTiempo
from .tareas import en_hilo
from .validacion_modelo import DialogoValidacionModelo
from .zonas import DialogoZonas


def _detalle_completo(c, escenario_id, version):
    detalle = servicios.escenario(c, escenario_id, version)
    return detalle, servicios.versiones(c, escenario_id)


def _estado_y_versiones(c, enfermedad_id):
    return servicios.estado_parametros(c, enfermedad_id), servicios.versiones_parametros(c, enfermedad_id)


def _catalogos(c):
    return servicios.enfermedades(c), servicios.regiones(c)


def texto_firma(f):
    # La firma de una versión aprobada (D55): lo que se aprobó contra lo que hoy se simularía y las corridas que lo simularon.
    if not f.get("firmada"):
        return "Firma: esta versión se aprobó antes de que se guardara la firma, así que no se puede verificar."
    corridas = f.get("corridas") or {}
    lineas = ["Firma: %s…" % (f.get("huella") or "")[:16] + " · aprobó %s el %s" % (f.get("revisor") or "—",
                                                                                   fecha(f.get("reviewed_at")))]
    if f.get("integra"):
        lineas.append("La entrada del motor sigue siendo la que se firmó.")
    else:
        lineas.append("ATENCIÓN: lo que hoy se simularía no coincide con lo que se aprobó (parámetros o intervenciones cambiaron).")
    lineas.append("Corridas que simularon exactamente lo firmado: %s; con otra entrada: %s; sin huella: %s." % (
        corridas.get("coinciden", 0), corridas.get("distintas", 0), corridas.get("sin_huella", 0)))
    return "\n".join(lineas)


def _parametros(params):
    return ", ".join("%s=%s" % (k, v) for k, v in (params or {}).items()) or "—"


class VistaEscenarios(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.c = ventana.cliente
        self.detalle = None
        self.historial_versiones = []
        self._solicitud = 0
        self._cargando_detalle = False
        self.tipos = []
        self.cargado = False

        self.b_validar = QPushButton("Validar")
        self.b_exportar = QPushButton("Exportar .xml")
        self.b_duplicar = QPushButton("Duplicar")
        self.b_version = QPushButton("Nueva versión")
        self.b_enviar = QPushButton("Enviar a revisión")
        self.b_lanzar = QPushButton("Lanzar corridas")
        self.b_lanzar.setObjectName("primario")
        botones = (self.b_validar, self.b_exportar, self.b_duplicar, self.b_version, self.b_enviar, self.b_lanzar)
        cabeza, self.titulo = encabezado("Escenarios", "Editor de escenario", botones)
        self.b_validar.clicked.connect(self.validar)
        self.b_exportar.clicked.connect(self.exportar)
        self.b_duplicar.clicked.connect(self.duplicar)
        self.b_version.clicked.connect(self.nueva_version)
        self.b_enviar.clicked.connect(self.enviar)
        self.b_lanzar.clicked.connect(self.lanzar)

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        cuerpo.addWidget(self._lista())
        cuerpo.addWidget(self._centro(), 1)
        cuerpo.addWidget(self._panel())
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(cabeza)
        capa.addLayout(cuerpo, 1)
        self._habilitar()

    def _lista(self):
        marco = QFrame()
        marco.setObjectName("panel")
        marco.setFixedWidth(250)
        capa = QVBoxLayout(marco)
        fila = QHBoxLayout()
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar escenario")
        self.buscar.returnPressed.connect(self.cargar_lista)
        nuevo = QPushButton("+")
        nuevo.setObjectName("primario")
        nuevo.setToolTip("Nuevo escenario")
        nuevo.clicked.connect(self.nuevo)
        fila.addWidget(self.buscar)
        fila.addWidget(nuevo)
        self.lista = QListWidget()
        self.lista.setWordWrap(True)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista.itemClicked.connect(lambda item: self.abrir(item.data(Qt.UserRole)))
        abrir = QPushButton("Abrir .xml local…")
        abrir.clicked.connect(self.abrir_xml)
        capa.addLayout(fila)
        capa.addWidget(self.lista, 1)
        nota = QLabel("Un .xml se valida con escenario.xsd antes de importarlo.")
        nota.setObjectName("nota")
        nota.setWordWrap(True)
        capa.addWidget(nota)
        capa.addWidget(abrir)
        return marco

    def _centro(self):
        contenido = QWidget()
        contenido.setObjectName("contenido")
        capa = QVBoxLayout(contenido)
        capa.setContentsMargins(16, 16, 16, 16)
        datos, rejilla = tarjeta()
        cuadro = QGridLayout()
        self.valores = {}
        for i, (clave, texto) in enumerate((("enfermedad", "Enfermedad"), ("region", "Región"),
                                            ("poblacion", "Población"), ("infectados", "Infectados iniciales"),
                                            ("horizonte", "Horizonte"))):
            caja, valor = dato_vertical(texto, "—")
            self.valores[clave] = valor
            cuadro.addWidget(caja, 0, i, Qt.AlignTop)
        rejilla.addLayout(cuadro)
        self.b_parametros = QPushButton("Consultar parámetros de la enfermedad")
        self.b_parametros.clicked.connect(self.consultar_parametros)
        self.b_ajustes = QPushButton("Ajustar parámetros de esta versión")
        self.b_ajustes.clicked.connect(self.abrir_ajustes)
        self.b_zonas = QPushButton("Indicadores municipales")
        self.b_zonas.clicked.connect(self.abrir_zonas)
        self.b_auditoria = QPushButton("Historial de auditoría")
        self.b_auditoria.clicked.connect(self.abrir_auditoria)
        self.b_modelo = QPushButton("Validación del modelo")
        self.b_modelo.clicked.connect(self.abrir_modelo)
        # En una sola fila, los cinco accesos eran más anchos que el centro de la ventana y obligaban
        # a desplazarse a lo ancho: van en una cuadrícula de dos por fila (con tres tampoco cabían a
        # 1440 px con la escala de 125 % de Windows).
        accesos = QGridLayout()
        for i, boton in enumerate((self.b_parametros, self.b_ajustes, self.b_zonas, self.b_auditoria,
                                   self.b_modelo)):
            accesos.addWidget(boton, i // 2, i % 2)
        accesos.setColumnStretch(2, 1)
        rejilla.addLayout(accesos)
        capa.addWidget(datos)

        linea, capa_linea = tarjeta("Línea de tiempo de intervenciones")
        self.linea = LineaTiempo()
        self.linea.seleccion.connect(lambda fila: self.intervenciones.selectRow(fila))
        capa_linea.addWidget(self.linea)
        self.intervenciones = tabla(["Intervención", "Días", "Cobertura", "Cumplimiento", "Parámetros"], estirar=(0, 4))
        self.intervenciones.setMinimumHeight(150)
        capa_linea.addWidget(self.intervenciones)
        acciones = QHBoxLayout()
        self.b_subir = QPushButton("Subir")
        self.b_bajar = QPushButton("Bajar")
        self.b_quitar = QPushButton("Quitar")
        self.b_quitar.setObjectName("peligro")
        self.b_subir.clicked.connect(lambda: self.mover("subir"))
        self.b_bajar.clicked.connect(lambda: self.mover("bajar"))
        self.b_quitar.clicked.connect(self.quitar)
        nota = QLabel("El orden es el de aplicación. Para cambiar una intervención, quítala y agrégala de nuevo.")
        nota.setObjectName("nota")
        nota.setWordWrap(True)
        acciones.addWidget(nota, 1)
        for b in (self.b_subir, self.b_bajar, self.b_quitar):
            acciones.addWidget(b)
        capa_linea.addLayout(acciones)
        capa.addWidget(linea)

        self.validacion = QLabel("Elige un escenario.")
        self.validacion.setObjectName("errores")
        self.validacion.setWordWrap(True)
        self.validacion.setTextFormat(Qt.RichText)
        capa.addWidget(self.validacion)
        self.firma = QLabel()
        self.firma.setObjectName("nota")
        self.firma.setWordWrap(True)
        self.firma.setTextFormat(Qt.PlainText)
        self.firma.hide()
        capa.addWidget(self.firma)
        capa.addStretch(1)
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
        pestanas = QTabWidget()
        nueva = QWidget()
        capa_nueva = QVBoxLayout(nueva)
        self.form = FormIntervencion()
        self.b_agregar = QPushButton("Agregar intervención")
        self.b_agregar.setObjectName("primario")
        self.b_agregar.clicked.connect(self.agregar)
        desplazar = QScrollArea()
        desplazar.setWidgetResizable(True)
        desplazar.setFrameShape(QFrame.NoFrame)
        desplazar.setWidget(self.form)
        capa_nueva.addWidget(desplazar, 1)
        capa_nueva.addWidget(self.b_agregar)
        historial = QWidget()
        capa_historial = QVBoxLayout(historial)
        self.versiones = QListWidget()
        self.versiones.setWordWrap(True)
        self.versiones.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.versiones.itemClicked.connect(lambda item: self.abrir(self.detalle["id"], item.data(Qt.UserRole)))
        nota = QLabel("Las versiones enviadas quedan congeladas (D5). Haz clic en una para verla.")
        nota.setObjectName("nota")
        nota.setWordWrap(True)
        capa_historial.addWidget(self.versiones)
        capa_historial.addWidget(nota)
        self.ficha_version = QLabel()
        self.ficha_version.setTextFormat(Qt.PlainText)
        self.ficha_version.setWordWrap(True)
        capa_historial.addWidget(self.ficha_version)
        pestanas.addTab(nueva, "Intervención")
        pestanas.addTab(historial, "Versiones")
        capa.addWidget(pestanas)
        return marco

    def al_mostrar(self):
        if not self.cargado:
            self.cargado = True
            self.cargar_lista()
            en_hilo(servicios.tipos_intervencion, self.c, listo=self._tipos)

    def _tipos(self, tipos):
        self.tipos = tipos
        self.form.poner_tipos(tipos, self._version().get("horizon_days") or 1095)

    def cargar_lista(self, seleccionar=None):
        en_hilo(servicios.escenarios, self.c, self.buscar.text().strip(),
                listo=lambda datos: self._lista_lista(datos, seleccionar))

    def _lista_lista(self, escenarios, seleccionar):
        self.lista.clear()
        actual = seleccionar or (self.detalle or {}).get("id")
        for e in escenarios:
            texto = "%s\n%s · v%s · %s" % (e["name"], estado(e.get("version_status"))[0],
                                         e.get("version_number"), e.get("autor") or "")
            item = QListWidgetItem(texto)
            item.setData(Qt.UserRole, e["id"])
            self.lista.addItem(item)
            if e["id"] == actual:
                self.lista.setCurrentItem(item)
        if seleccionar:
            self.abrir(seleccionar)

    def abrir(self, escenario_id, version=None):
        self._solicitud += 1
        solicitud = self._solicitud
        self._cargando_detalle = True
        self.validacion.setText("Cargando la versión solicitada…")
        self._habilitar()
        en_hilo(_detalle_completo, self.c, escenario_id, version,
                listo=lambda datos: self._mostrar(datos, solicitud),
                fallo=lambda exc: self._fallo_detalle(exc, solicitud))

    def _fallo_detalle(self, exc, solicitud):
        if solicitud != self._solicitud:
            return
        self._cargando_detalle = False
        self.validacion.setText("No se pudo abrir la versión solicitada.")
        self._habilitar()
        self.v.mostrar_error(exc)

    def _version(self):
        return (self.detalle or {}).get("version") or {}

    def _mostrar(self, resultado, solicitud):
        if solicitud != self._solicitud:
            return
        self._cargando_detalle = False
        self.detalle, versiones = resultado
        self.historial_versiones = versiones
        d, v = self.detalle, self._version()
        self.titulo.setText("%s · %s v%s" % (d["name"], estado(v.get("status"))[0], v.get("version_number")))
        self.valores["enfermedad"].setText(d.get("enfermedad") or "—")
        self.valores["region"].setText(d.get("region") or "—")
        self.valores["poblacion"].setText(num(v.get("population_size")) + (" · por edad" if v.get("por_edad") else ""))
        self.valores["infectados"].setText(num(v.get("initial_infected")))
        self.valores["horizonte"].setText("%s días" % v.get("horizon_days"))
        intervenciones = d.get("intervenciones") or []
        self.linea.poner(intervenciones, v.get("horizon_days"))
        self.intervenciones.setRowCount(0)
        for iv in intervenciones:
            fila = self.intervenciones.rowCount()
            self.intervenciones.insertRow(fila)
            fin = "fin" if iv.get("end_day") is None else iv["end_day"]
            valores = (iv.get("name") or iv["code"], "%s–%s" % (iv["start_day"], fin),
                       num(iv.get("coverage"), 2), num(iv.get("compliance"), 2), _parametros(iv.get("params")))
            for col, valor in enumerate(valores):
                self.intervenciones.setItem(fila, col, celda(valor, dato=iv["id"] if col == 0 else None))
        self.versiones.clear()
        for ver in versiones:
            item = QListWidgetItem("v%s · %s%s\n%s · %s\n%s" % (
                ver["version_number"], estado(ver["status"])[0], " · vigente" if ver.get("is_current") else "",
                ver.get("autor") or "Autor sin dato", fecha(ver.get("created_at")), ver.get("notes") or ""))
            item.setData(Qt.UserRole, ver["version_number"])
            self.versiones.addItem(item)
        self.ficha_version.setText("Versión seleccionada: v%s\nAutor: %s\nEnvío: %s\nRevisión: %s\nRevisor: %s" % (
            v.get("version_number") or "—", v.get("autor") or d.get("autor") or "—",
            fecha(v.get("submitted_at")), fecha(v.get("reviewed_at")), v.get("revisor") or "—"))
        if self.tipos:
            self.form.poner_tipos(self.tipos, v.get("horizon_days") or 1095)
        self._habilitar()
        self.validar()
        self._cargar_firma(v, solicitud)

    def _cargar_firma(self, v, solicitud):
        self.firma.hide()
        if v.get("status") != "aprobado" or not v.get("id"):
            return

        def listo(datos):
            if solicitud == self._solicitud:
                self.firma.setText(texto_firma(datos))
                self.firma.show()

        # La firma es un dato de apoyo: si aprobacion no responde, la pantalla sigue como estaba.
        en_hilo(servicios.firma_version, self.c, v["id"], listo=listo, fallo=lambda exc: None)

    def _mostrar_validacion(self, datos):
        errores = datos.get("errores") or []
        avisos = datos.get("avisos") or []
        partes = ['<span style="background:%s;padding:2px">%d errores</span>' % (
                      "#FEE2E2" if errores else "#DCFCE7", len(errores)),
                  '<span style="background:#FEF3C7;padding:2px">%d advertencias</span>' % len(avisos)]
        detalle = "".join("<br>• %s" % escape(
            "%s: %s" % (e.get("ruta") or "Campo", e.get("mensaje") or "Sin detalle")
            if isinstance(e, dict) else str(e)) for e in errores + avisos)
        revision = ""
        v = self._version()
        if v.get("review_comment"):
            revision = "<b>Comentario de la revisión%s:</b> %s<br><br>" % (
                " (%s)" % escape(v["revisor"]) if v.get("revisor") else "", escape(v["review_comment"]))
        resultado = {True: "Válida", False: "Con errores"}.get(datos.get("valido"), "Estado sin dato")
        self.validacion.setText("%sValidación del escenario: <b>%s</b> · %s%s"
                               % (revision, resultado, " ".join(partes), detalle))

    def _propio(self):
        dueno = (self.detalle or {}).get("owner_id")
        return self.v.es_admin() or (dueno is not None and dueno == (self.c.usuario or {}).get("id"))

    def _editable(self):
        return bool(self.detalle and self.detalle.get("editable") and self._propio())

    def _habilitar(self):
        hay = self.detalle is not None and not self._cargando_detalle
        editable = hay and self._editable()
        for b in (self.b_validar, self.b_exportar, self.b_duplicar):
            b.setEnabled(hay)
        self.b_parametros.setEnabled(bool(hay and self.detalle.get("disease_id")))
        self.b_ajustes.setEnabled(bool(hay and self._version().get("id") and self.detalle.get("disease_id")))
        self.b_zonas.setEnabled(self.b_parametros.isEnabled())
        self.b_auditoria.setEnabled(hay)
        self.b_modelo.setEnabled(bool(hay and self.detalle.get("disease_id") and self.detalle.get("region_id")))
        self.b_version.setEnabled(hay and self._propio() and bool(self._version().get("is_current"))
                                  and self._version().get("status") != "borrador")
        for b in (self.b_enviar, self.b_agregar, self.b_subir, self.b_bajar, self.b_quitar):
            b.setEnabled(editable)
        self.b_lanzar.setEnabled(hay and self._version().get("status") == "aprobado")

    def _recargar(self, *_):
        if self.detalle:
            self.abrir(self.detalle["id"])
        self.cargar_lista()

    def _intervencion_elegida(self):
        fila = self.intervenciones.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Escenarios", "Elige una intervención de la tabla.")
            return None
        return self.intervenciones.item(fila, 0).data(Qt.UserRole)

    def nuevo(self):
        en_hilo(_catalogos, self.c, listo=self._dialogo_nuevo)

    def _dialogo_nuevo(self, catalogos):
        dialogo = DialogoEscenario(self, *catalogos)
        if dialogo.exec():
            datos = dialogo.datos()
            self.v.accion("crea el escenario «%s»" % datos["name"])
            en_hilo(servicios.crear_escenario, self.c, datos,
                    listo=lambda r: self.cargar_lista(seleccionar=r["id"]))

    def nueva_version(self):
        dialogo = DialogoVersion(self, self._version())
        if dialogo.exec():
            self.v.accion("crea una versión del escenario %s" % self.detalle["id"])
            en_hilo(servicios.crear_version, self.c, self.detalle["id"], dialogo.datos(), listo=self._recargar)

    def duplicar(self):
        nombre, ok = QInputDialog.getText(self, "Duplicar escenario", "Nombre de la copia",
                                          text="%s (copia)" % self.detalle["name"])
        if ok and nombre.strip():
            self.v.accion("duplica el escenario %s" % self.detalle["id"])
            en_hilo(servicios.duplicar, self.c, self.detalle["id"], nombre.strip(),
                    self._version()["version_number"], listo=lambda r: self.cargar_lista(seleccionar=r["id"]))

    def agregar(self):
        try:
            datos = self.form.datos()
        except ValueError as exc:
            QMessageBox.warning(self, "Intervención", str(exc))
            return
        self.v.accion("agrega %s a la versión %s" % (datos["code"], self._version()["id"]))
        en_hilo(servicios.agregar_intervencion, self.c, self._version()["id"], datos, listo=self._recargar)

    def quitar(self):
        iid = self._intervencion_elegida()
        if iid and QMessageBox.question(self, "Quitar", "¿Quitar esta intervención?") == QMessageBox.Yes:
            self.v.accion("quita la intervención %s" % iid)
            en_hilo(servicios.quitar_intervencion, self.c, self._version()["id"], iid, listo=self._recargar)

    def mover(self, direccion):
        iid = self._intervencion_elegida()
        if iid:
            en_hilo(servicios.mover_intervencion, self.c, self._version()["id"], iid, direccion,
                    listo=self._recargar)

    def validar(self):
        version_id = self._version().get("id")
        if not version_id:
            self.validacion.setText("El escenario todavía no tiene una versión para validar.")
            return
        solicitud = self._solicitud
        self.validacion.setText("Consultando la validación del servidor…")
        en_hilo(servicios.validar_version, self.c, version_id,
                listo=lambda datos: self._validada(datos, solicitud),
                fallo=lambda exc: self._fallo_validacion(exc, solicitud))

    def _validada(self, datos, solicitud):
        if solicitud == self._solicitud:
            self._mostrar_validacion(datos)

    def _fallo_validacion(self, exc, solicitud):
        if solicitud != self._solicitud:
            return
        self.validacion.setText("Validación del servidor no disponible. Usa Validar para reintentar.")
        if isinstance(exc, api.SesionCerrada):
            self.v.mostrar_error(exc)

    def consultar_parametros(self):
        enfermedad_id = self.detalle["disease_id"]
        nombre = self.detalle.get("enfermedad") or "Enfermedad %s" % enfermedad_id
        en_hilo(_estado_y_versiones, self.c, enfermedad_id,
                listo=lambda datos: mostrar_parametros(self, nombre, *datos))

    def abrir_ajustes(self):
        d = self.detalle
        dialogo = DialogoAjustes(self, self.v, self._version()["id"], d.get("enfermedad") or "Enfermedad",
                                 self._editable())
        # Un ajuste cambia los avisos de la validación: se consultan otra vez al cerrar.
        dialogo.finished.connect(lambda _: self.validar())
        dialogo.open()

    def abrir_zonas(self):
        d = self.detalle
        DialogoZonas(self, self.v, d["disease_id"], d.get("enfermedad") or "Enfermedad").open()

    def abrir_auditoria(self):
        if self.detalle and not self._cargando_detalle:
            DialogoAuditoria(self, self.v, self.detalle, self.historial_versiones).open()

    def abrir_modelo(self):
        DialogoValidacionModelo(self, self.v, self.detalle).open()

    def enviar(self):
        pregunta = ("Al enviarla, la versión %s queda congelada y un epidemiólogo la revisa en la web. ¿Enviar?"
                    % self._version()["version_number"])
        if QMessageBox.question(self, "Enviar a revisión", pregunta) == QMessageBox.Yes:
            self.v.accion("envía a revisión el escenario %s" % self.detalle["id"])
            en_hilo(servicios.enviar_a_revision, self.c, self.detalle["id"], listo=self._enviado)

    def _enviado(self, datos):
        avisos = datos.get("avisos") or []
        texto = "La versión quedó en revisión."
        if avisos:
            texto += "\n\nAvisos:\n" + "\n".join("• %s" % a for a in avisos)
        QMessageBox.information(self, "Enviar a revisión", texto)
        self._recargar()

    def lanzar(self):
        v = self._version()
        self.v.lanzar_corridas({"version_id": v["id"], "nombre": "%s · v%s" % (self.detalle["name"],
                                                                             v["version_number"])})

    def exportar(self):
        v = self._version()
        nombre = "escenario-%s-v%s.xml" % (self.detalle["id"], v["version_number"])
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar escenario", nombre, "XML (*.xml)")
        if ruta:
            self.v.accion("exporta el escenario %s v%s a %s" % (self.detalle["id"], v["version_number"], ruta))
            en_hilo(servicios.exportar_xml, self.c, self.detalle["id"], v["version_number"],
                    listo=lambda contenido: self._guardado(ruta, contenido))

    def _guardado(self, ruta, contenido):
        Path(ruta).write_bytes(contenido)
        QMessageBox.information(self, "Exportar", "Guardado en %s.\nEs válido contra escenario.xsd." % ruta)

    def abrir_xml(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir escenario", "", "XML (*.xml)")
        if not ruta:
            return
        contenido = Path(ruta).read_bytes()
        dialogo = DialogoXML(self, ruta, contenido)
        if dialogo.exec():
            self.v.accion("importa el escenario de %s" % ruta)
            en_hilo(servicios.importar_xml, self.c, contenido, listo=self._importado)

    def _importado(self, datos):
        avisos = datos.get("avisos") or []
        texto = "Se creó el escenario %s con %s intervenciones." % (datos["scenario_id"],
                                                                     datos.get("intervenciones_creadas", 0))
        if avisos:
            texto += "\n\nAvisos:\n" + "\n".join("• %s" % a for a in avisos)
        QMessageBox.information(self, "Importar", texto)
        self.cargar_lista(seleccionar=datos["scenario_id"])


def resumen_xml(contenido):
    raiz = XMLSeguro.fromstring(contenido)
    version = raiz.find("version")
    lineas = ["Nombre: %s" % raiz.findtext("nombre"),
              "Enfermedad: %s · Región: %s" % (raiz.find("enfermedad").get("codigo"), raiz.find("region").get("codigo")),
              "Versión %s · población %s · %s días · %s infectados iniciales" % (
                  version.get("numero"), version.find("poblacion").get("total"),
                  version.findtext("horizonte_dias"), version.findtext("infectados_iniciales")),
              "", "Intervenciones:"]
    for iv in version.iter("intervencion"):
        parametros = ", ".join("%s=%s" % (p.get("nombre"), p.text) for p in iv.iter("parametro"))
        lineas.append("  %s · días %s–%s · %s" % (iv.get("tipo"), iv.findtext("inicio_dia"),
                                                  iv.findtext("fin_dia") or "fin", parametros or "sin parámetros"))
    return "\n".join(lineas)


class DialogoXML(QDialog):
    def __init__(self, padre, ruta, contenido):
        super().__init__(padre)
        self.setWindowTitle("Escenario local · %s" % Path(ruta).name)
        self.setMinimumSize(620, 460)
        texto = QPlainTextEdit()
        texto.setReadOnly(True)
        estado_xsd = QLabel()
        estado_xsd.setWordWrap(True)
        botones = QDialogButtonBox()
        importar = botones.addButton("Importar al servidor", QDialogButtonBox.AcceptRole)
        botones.addButton(QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        try:
            esquemas.validar_escenario(contenido)
            estado_xsd.setText("✔ Válido contra escenario.xsd.")
            estado_xsd.setStyleSheet("color: #15803D;")
            texto.setPlainText(resumen_xml(contenido))
        except esquemas.XMLInvalido as exc:
            importar.setEnabled(False)
            estado_xsd.setText("✖ No cumple escenario.xsd (%d fallas). Corrige el archivo antes de importarlo."
                               % len(exc.errores))
            estado_xsd.setStyleSheet("color: #B91C1C;")
            texto.setPlainText("\n".join("%s: %s" % (e["ruta"], e["mensaje"]) for e in exc.errores))
        except Exception as exc:
            importar.setEnabled(False)
            estado_xsd.setText("✖ El archivo no es XML legible: %s" % exc)
            estado_xsd.setStyleSheet("color: #B91C1C;")
        capa = QVBoxLayout(self)
        capa.addWidget(estado_xsd)
        capa.addWidget(texto, 1)
        capa.addWidget(botones)
