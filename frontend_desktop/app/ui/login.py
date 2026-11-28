from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import api, config, servicios
from .tareas import en_hilo

# Con estos errores el reto sigue vivo y se puede intentar otro código; con cualquier otro (vencido,
# bloqueado, rol sin acceso al escritorio) hay que volver a escribir la contraseña (D40).
REINTENTABLES = ("MFA_CODIGO_INVALIDO", "DATOS_INVALIDOS", "ALTA_REQUERIDA", "ALTA_INVALIDA")


class DialogoLogin(QDialog):
    def __init__(self, cliente, motivo=""):
        super().__init__()
        self.cliente = cliente
        self.captcha_id = None
        self.mfa_token = None
        self.enrolado = False
        self.setWindowTitle("EPIDEMIA · Iniciar sesión")
        self.setMinimumWidth(420)

        marca = QLabel("EPIDEMIA")
        marca.setObjectName("titulo")
        sub = QLabel("Simulación de brotes · app de escritorio")
        sub.setObjectName("nota")
        self.mensaje = QLabel(motivo)
        self.mensaje.setWordWrap(True)
        self.mensaje.setStyleSheet("color: #B91C1C;")
        servidor = QLabel("Directorio: %s" % config.DIRECTORIO)
        servidor.setObjectName("nota")

        self.pasos = QStackedWidget()
        self.pasos.addWidget(self._paso_credenciales())
        self.pasos.addWidget(self._paso_mfa())

        capa = QVBoxLayout(self)
        capa.setContentsMargins(28, 24, 28, 24)
        capa.addWidget(marca)
        capa.addWidget(sub)
        capa.addSpacing(12)
        capa.addWidget(self.pasos)
        capa.addWidget(self.mensaje)
        capa.addWidget(servidor)
        self.cargar_captcha()

    def _paso_credenciales(self):
        pagina = QWidget()
        self.usuario = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.pregunta = QLabel("Cargando…")
        self.respuesta = QLineEdit()
        self.respuesta.setPlaceholderText("Resultado")
        otra = QPushButton("Otra pregunta")
        otra.clicked.connect(self.cargar_captcha)
        self.entrar = QPushButton("Entrar")
        self.entrar.setObjectName("primario")
        self.entrar.setDefault(True)
        self.entrar.clicked.connect(self.iniciar)

        forma = QFormLayout()
        forma.addRow("Usuario o correo", self.usuario)
        forma.addRow("Contraseña", self.password)
        fila = QHBoxLayout()
        fila.addWidget(self.pregunta, 1)
        fila.addWidget(otra)
        forma.addRow("¿Cuánto es?", fila)
        forma.addRow("", self.respuesta)
        capa = QVBoxLayout(pagina)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.addLayout(forma)
        capa.addWidget(self.entrar, alignment=Qt.AlignRight)
        return pagina

    def _paso_mfa(self):
        pagina = QWidget()
        self.explicacion = QLabel()
        self.explicacion.setWordWrap(True)
        self.alta = QLineEdit()
        self.alta.setPlaceholderText("Código de alta que te dio un administrador")
        self.generar = QPushButton("Generar mi secreto")
        self.generar.clicked.connect(self.enrolar)
        self.secreto = QLabel()
        self.secreto.setWordWrap(True)
        self.secreto.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.codigo = QLineEdit()
        self.codigo.setPlaceholderText("Código de 6 dígitos")
        self.verificar = QPushButton("Verificar")
        self.verificar.setObjectName("primario")
        self.verificar.clicked.connect(self.enviar_codigo)
        volver = QPushButton("Volver")
        volver.clicked.connect(self.volver)

        capa = QVBoxLayout(pagina)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.addWidget(self.explicacion)
        fila_alta = QHBoxLayout()
        fila_alta.addWidget(self.alta, 1)
        fila_alta.addWidget(self.generar)
        capa.addLayout(fila_alta)
        capa.addWidget(self.secreto)
        capa.addWidget(self.codigo)
        botones = QHBoxLayout()
        botones.addWidget(volver)
        botones.addStretch(1)
        botones.addWidget(self.verificar)
        capa.addLayout(botones)
        return pagina

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
                self.captcha_id, self.respuesta.text().strip(), listo=self._entro, fallo=self._fallo)

    def _entro(self, datos):
        if isinstance(datos, dict) and datos.get("mfa_requerido"):
            self.mostrar_mfa(datos)
            return
        self.accept()

    def mostrar_mfa(self, reto):
        self.mfa_token = reto["mfa_token"]
        self.enrolado = bool(reto.get("mfa_enrolado"))
        self.password.clear()
        self.entrar.setEnabled(True)
        self.codigo.clear()
        self.alta.clear()
        self.secreto.clear()
        self.mensaje.setText("")
        if self.enrolado:
            self.explicacion.setText("Tu perfil pide un segundo paso. Escribe el código de 6 dígitos de tu "
                                     "app de autenticación o uno de tus códigos de respaldo.")
            self.codigo.setPlaceholderText("Código de 6 dígitos o de respaldo")
        else:
            self.explicacion.setText("Tu perfil pide un segundo paso y aún no lo has activado. Pide a un "
                                     "administrador tu código de alta, genera tu secreto, regístralo en tu "
                                     "app de autenticación y escribe el primer código.")
            self.codigo.setPlaceholderText("Código de 6 dígitos")
        for widget in (self.alta, self.generar):
            widget.setVisible(not self.enrolado)
        self.codigo.setEnabled(self.enrolado)
        self.verificar.setEnabled(self.enrolado)
        self.pasos.setCurrentIndex(1)

    def enrolar(self):
        if not self.alta.text().strip():
            self.mensaje.setText("Escribe el código de alta que te dio un administrador.")
            return
        self.generar.setEnabled(False)
        self.mensaje.setText("")
        en_hilo(partial(servicios.segundo_paso, codigo_alta=self.alta.text().strip()), self.cliente, "enroll",
                self.mfa_token, listo=self._secreto, fallo=self._fallo_mfa)

    def _secreto(self, datos):
        self.generar.setEnabled(True)
        self.secreto.setText("Registra este secreto en tu app de autenticación (TOTP, %s dígitos cada %s s):\n%s\n\n%s"
                             % (datos.get("digitos", 6), datos.get("periodo", 30), datos.get("secreto", ""),
                                datos.get("uri", "")))
        self.codigo.setEnabled(True)
        self.verificar.setEnabled(True)
        self.codigo.setFocus()

    def enviar_codigo(self):
        codigo = self.codigo.text().strip()
        if not codigo:
            self.mensaje.setText("Escribe el código.")
            return
        self.verificar.setEnabled(False)
        self.mensaje.setText("")
        accion = "verify" if self.enrolado else "confirm"
        en_hilo(partial(servicios.segundo_paso, codigo=codigo), self.cliente, accion, self.mfa_token,
                listo=self._completo, fallo=self._fallo_mfa)

    def _completo(self, datos):
        respaldos = datos.get("codigos_respaldo") or []
        if respaldos:
            caja = QMessageBox(QMessageBox.Information, "EPIDEMIA",
                               "Guarda tus códigos de respaldo. Cada uno sirve una sola vez y no se volverán "
                               "a mostrar.", parent=self)
            caja.setDetailedText("\n".join(respaldos))
            caja.exec()
        self.accept()

    def _fallo_mfa(self, exc):
        self.verificar.setEnabled(self.codigo.isEnabled())
        self.generar.setEnabled(True)
        self.codigo.clear()
        sin_respuesta = isinstance(exc, api.ErrorServicio) and exc.status is None
        if not (sin_respuesta or getattr(exc, "codigo", None) in REINTENTABLES):
            self.volver()
        self._error(exc)

    def volver(self):
        self.mfa_token = None
        self.pasos.setCurrentIndex(0)
        self.entrar.setEnabled(True)
        self.cargar_captcha()

    def _fallo(self, exc):
        self.entrar.setEnabled(True)
        self.password.clear()
        self._error(exc)
        self.cargar_captcha()

    def _error(self, exc):
        self.mensaje.setText(str(exc))
