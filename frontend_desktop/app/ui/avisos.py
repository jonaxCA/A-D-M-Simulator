from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout

from .. import servicios
from .comun import fecha
from .tareas import en_hilo


class DialogoAvisos(QDialog):
    def __init__(self, ventana):
        super().__init__(ventana)
        self.v = ventana
        self.setWindowTitle("Avisos")
        self.setMinimumSize(520, 420)
        self.lista = QListWidget()
        self.estado = QLabel("Cargando…")
        self.estado.setObjectName("nota")
        leer = QPushButton("Marcar como leído")
        leer.clicked.connect(self.marcar)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        botones = QHBoxLayout()
        botones.addWidget(self.estado, 1)
        botones.addWidget(leer)
        botones.addWidget(cerrar)
        capa = QVBoxLayout(self)
        capa.addWidget(self.lista)
        capa.addLayout(botones)
        self.cargar()

    def cargar(self):
        en_hilo(servicios.avisos, self.v.cliente, listo=self._mostrar)

    def _mostrar(self, datos):
        self.lista.clear()
        for a in datos.get("notificaciones") or []:
            marca = "" if a.get("read_at") else "● "
            item = QListWidgetItem("%s%s\n%s\n%s" % (marca, a.get("title"), a.get("body") or "", fecha(a.get("created_at"))))
            item.setData(Qt.UserRole, a["id"])
            self.lista.addItem(item)
        self.estado.setText("%s sin leer de %s" % (datos.get("no_leidas", 0), datos.get("total", 0)))

    def marcar(self):
        item = self.lista.currentItem()
        if item:
            en_hilo(servicios.marcar_leido, self.v.cliente, item.data(Qt.UserRole), listo=lambda _: self.cargar())
