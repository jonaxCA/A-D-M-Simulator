from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout)

from .. import config, servicios
from .tareas import en_hilo


class DialogoLogin(QDialog):
    def __init__(self, cliente, motivo=""):
        super().__init__()
        self.cliente = cliente
        self.captcha_id = None
        self.setWindowTitle("EPIDEMIA · Iniciar sesión")
        self.setMinimumWidth(400)

        marca = QLabel("EPIDEMIA")
        marca.setObjectName("titulo")
        sub = QLabel("Simulación de brotes · app de escritorio")
        sub.setObjectName("nota")
        self.usuario = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.pregunta = QLabel("Cargando…")
        self.respuesta = QLineEdit()
        self.respuesta.setPlaceholderText("Resultado")
        otra = QPushButton("Otra pregunta")
        otra.clicked.connect(self.cargar_captcha)
        self.mensaje = QLabel(motivo)
        self.mensaje.setWordWrap(True)
        self.mensaje.setStyleSheet("color: #B91C1C;")
        self.entrar = QPushButton("Entrar")
        self.entrar.setObjectName("primario")
        self.entrar.setDefault(True)
        self.entrar.clicked.connect(self.iniciar)
        servidor = QLabel("Directorio: %s" % config.DIRECTORIO)
        servidor.setObjectName("nota")

        forma = QFormLayout()
        forma.addRow("Usuario o correo", self.usuario)
        forma.addRow("Contraseña", self.password)
        fila = QHBoxLayout()
        fila.addWidget(self.pregunta, 1)
        fila.addWidget(otra)
        forma.addRow("¿Cuánto es?", fila)
        forma.addRow("", self.respuesta)

        capa = QVBoxLayout(self)
        capa.setContentsMargins(28, 24, 28, 24)
        capa.addWidget(marca)
        capa.addWidget(sub)
        capa.addSpacing(12)
        capa.addLayout(forma)
        capa.addWidget(self.mensaje)
        capa.addWidget(self.entrar, alignment=Qt.AlignRight)
        capa.addWidget(servidor)
        self.cargar_captcha()

    def cargar_captcha(self):
        self.pregunta.setText("Cargando…")
        self.respuesta.clear()
        en_hilo(servicios.captcha, self.cliente, listo=self._captcha, fallo=self._error)

    def _captcha(self, datos):
        self.captcha_id = datos["captcha_id"]
        self.pregunta.setText(datos["pregunta"])

    def iniciar(self):
        if not (self.usuario.text().strip() and self.password.text() and self.respuesta.text().strip()):
            self.mensaje.setText("Escribe usuario, contraseña y el resultado de la pregunta.")
            return
        self.entrar.setEnabled(False)
        self.mensaje.setText("")
        en_hilo(servicios.abrir_sesion, self.cliente, self.usuario.text().strip(), self.password.text(),
                self.captcha_id, self.respuesta.text().strip(), listo=lambda _: self.accept(), fallo=self._fallo)

    def _fallo(self, exc):
        self.entrar.setEnabled(True)
        self.password.clear()
        self._error(exc)
        self.cargar_captcha()

    def _error(self, exc):
        self.mensaje.setText(str(exc))
