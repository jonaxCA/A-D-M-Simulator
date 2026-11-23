import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QVBoxLayout)

from .. import api, servicios
from .comun import celda, fecha, tabla
from .tareas import en_hilo


LIMITE = 50
ACCIONES = {"CREATE": "Creación", "INSERT": "Creación", "UPDATE": "Modificación",
            "DELETE": "Eliminación", "APPROVE": "Aprobación", "REJECT": "Rechazo", "SUBMIT": "Envío a revisión"}
ESTADOS = {"aprobado": "Aprobación", "rechazado": "Rechazo", "en_revision": "Envío a revisión"}


def _pagina(c, escenario_id, entidad, identificador, numero, offset):
    if identificador is None:
        version = servicios.escenario(c, escenario_id, numero).get("version") or {}
        identificador = version.get("id")
        if identificador is None or version.get("version_number") != numero:
            raise api.ErrorServicio("No se encontró el identificador de la versión solicitada.")
    return servicios.historial_auditoria(c, entidad, identificador, LIMITE, offset)


def _accion(evento):
    accion = evento.get("accion")
    if accion == "UPDATE":
        antes, despues = evento.get("antes") or {}, evento.get("datos") or {}
        estado = despues.get("status")
        if estado != antes.get("status") and estado in ESTADOS:
            return "%s (%s)" % (ESTADOS[estado], accion)
    return "%s (%s)" % (ACCIONES[accion], accion) if accion in ACCIONES else accion


class DialogoAuditoria(QDialog):
    def __init__(self, padre, ventana, escenario, versiones):
        super().__init__(padre)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Historial de auditoría · %s" % escenario["name"])
        self.resize(780, 580)
        self.ventana = ventana
        self.escenario_id = escenario["id"]
        self.offset = self.total = 0
        self.eventos = []
        capa = QVBoxLayout(self)
        self.entidad = QComboBox()
        self.entidad.addItem("Escenario", ("scenarios", escenario["id"], None))
        actual = escenario.get("version") or {}
        por_numero = {v["version_number"]: v.get("id") for v in versiones}
        if actual.get("version_number") is not None:
            por_numero[actual["version_number"]] = actual.get("id")
        for numero, identificador in sorted(por_numero.items(), reverse=True):
            self.entidad.addItem("Versión %d" % numero, ("scenario_versions", identificador, numero))
        for iv in escenario.get("intervenciones") or []:
            self.entidad.addItem("Intervención · %s (#%s)" % (iv.get("name") or iv.get("code"), iv["id"]),
                                 ("scenario_interventions", iv["id"], None))
        capa.addWidget(self.entidad)
        self.tabla = tabla(["Fecha", "Usuario", "Acción", "Evento"], estirar=(1, 2))
        self.tabla.currentCellChanged.connect(self._detalle)
        capa.addWidget(self.tabla, 1)
        self.detalle = QPlainTextEdit()
        self.detalle.setReadOnly(True)
        self.detalle.setPlaceholderText("Selecciona un evento para ver los campos antes y después.")
        capa.addWidget(self.detalle, 1)
        pie = QHBoxLayout()
        self.estado = QLabel()
        self.estado.setTextFormat(Qt.PlainText)
        self.estado.setWordWrap(True)
        pie.addWidget(self.estado, 1)
        self.anterior = QPushButton("Anterior")
        self.siguiente = QPushButton("Siguiente")
        self.anterior.clicked.connect(lambda: self.cargar(max(0, self.offset - LIMITE)))
        self.siguiente.clicked.connect(lambda: self.cargar(self.offset + LIMITE))
        pie.addWidget(self.anterior)
        pie.addWidget(self.siguiente)
        capa.addLayout(pie)
        botones = QDialogButtonBox(QDialogButtonBox.Close)
        botones.button(QDialogButtonBox.Close).setText("Cerrar")
        botones.rejected.connect(self.reject)
        capa.addWidget(botones)
        self.entidad.currentIndexChanged.connect(lambda: self.cargar(0))
        self.cargar(0)

    def cargar(self, offset):
        self.entidad.setEnabled(False)
        self.anterior.setEnabled(False)
        self.siguiente.setEnabled(False)
        self.tabla.setRowCount(0)
        self.detalle.clear()
        self.estado.setText("Consultando auditoría del servidor…")
        en_hilo(_pagina, self.ventana.cliente, self.escenario_id, *self.entidad.currentData(), offset,
                listo=self._mostrar, fallo=self._fallo)

    def _mostrar(self, datos):
        self.eventos = datos.get("eventos") or []
        self.offset = datos.get("offset", 0)
        self.total = datos.get("coincidencias", len(self.eventos))
        self.tabla.setRowCount(len(self.eventos))
        for fila, ev in enumerate(self.eventos):
            valores = (fecha(ev.get("fecha")), ev.get("usuario") or "Sin usuario informado", _accion(ev), ev.get("id"))
            for col, valor in enumerate(valores):
                self.tabla.setItem(fila, col, celda(valor))
        self.entidad.setEnabled(True)
        self.anterior.setEnabled(self.offset > 0)
        self.siguiente.setEnabled(bool(self.eventos) and self.offset + len(self.eventos) < self.total)
        if self.eventos:
            self.estado.setText("%d–%d de %d eventos" % (self.offset + 1, self.offset + len(self.eventos), self.total))
            self.tabla.selectRow(0)
        else:
            self.estado.setText("El servidor no devolvió eventos en esta página.")

    def _detalle(self, fila, *_):
        if 0 <= fila < len(self.eventos):
            ev = self.eventos[fila]
            antes = json.dumps(ev.get("antes"), ensure_ascii=False, indent=2)
            despues = json.dumps(ev.get("datos"), ensure_ascii=False, indent=2)
            self.detalle.setPlainText("Antes\n%s\n\nDespués\n%s" % (antes, despues))
        else:
            self.detalle.clear()

    def _fallo(self, exc):
        self.entidad.setEnabled(True)
        if isinstance(exc, api.ErrorServicio) and exc.status == 403:
            self.estado.setText("Tu cuenta no tiene acceso al historial de esta entidad.")
        else:
            self.estado.setText("El servidor no devolvió el historial.")
            self.ventana.mostrar_error(exc)
