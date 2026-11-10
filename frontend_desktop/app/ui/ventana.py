from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import api, bitacora, config, servicios
from . import tareas
from .avisos import DialogoAvisos
from .comparacion import VistaComparacion
from .comun import NOMBRES_ROL
from .escenarios import VistaEscenarios
from .login import DialogoLogin
from .simulaciones import VistaSimulaciones
from .tareas import en_hilo

AVISO_PIE = "Proyecto académico · no constituye asesoría sanitaria"


class Ventana(QMainWindow):
    def __init__(self, cliente):
        super().__init__()
        self.cliente = cliente
        self.reingresando = False
        tareas.manejador_errores = self.mostrar_error
        self.setWindowTitle("EPIDEMIA · Simulación de brotes")
        self.resize(1440, 900)

        self.escenarios = VistaEscenarios(self)
        self.simulaciones = VistaSimulaciones(self)
        self.comparacion = VistaComparacion(self)
        self.pila = QStackedWidget()
        self.pila.setObjectName("contenido")
        for vista in (self.escenarios, self.simulaciones, self.comparacion):
            self.pila.addWidget(vista)

        cuerpo = QWidget()
        capa = QHBoxLayout(cuerpo)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(self._lateral())
        capa.addWidget(self.pila, 1)
        self.setCentralWidget(cuerpo)
        self._barra_estado()

        self.temporizadores = []
        for segundos, fn in ((config.SEGUNDOS_SALUD, self.revisar_salud),
                             (config.SEGUNDOS_SESION, self.revisar_sesion),
                             (config.SEGUNDOS_AVISOS, self.revisar_avisos)):
            t = QTimer(self)
            t.timeout.connect(fn)
            t.start(segundos * 1000)
            self.temporizadores.append(t)
        self.ir(0)
        self.revisar_salud()
        self.revisar_avisos()

    def _lateral(self):
        lateral = QFrame()
        lateral.setObjectName("lateral")
        lateral.setFixedWidth(200)
        capa = QVBoxLayout(lateral)
        capa.setContentsMargins(12, 16, 12, 16)
        marca = QLabel("EPIDEMIA")
        marca.setObjectName("marca")
        sub = QLabel("Simulación de brotes")
        sub.setObjectName("submarca")
        seccion = QLabel("TRABAJO")
        seccion.setObjectName("seccionLateral")
        capa.addWidget(marca)
        capa.addWidget(sub)
        capa.addWidget(seccion)
        self.grupo = QButtonGroup(self)
        for i, nombre in enumerate(("Escenarios", "Simulaciones", "Comparación")):
            boton = QPushButton("%s\tCtrl+%d" % (nombre, i + 1))
            boton.setCheckable(True)
            boton.clicked.connect(lambda _=False, i=i: self.ir(i))
            self.grupo.addButton(boton, i)
            capa.addWidget(boton)
            QShortcut(QKeySequence("Ctrl+%d" % (i + 1)), self, activated=lambda i=i: self.ir(i))
        capa.addStretch(1)
        self.nombre = QLabel()
        self.nombre.setObjectName("usuarioLateral")
        self.nombre.setWordWrap(True)
        self.rol = QLabel()
        self.rol.setObjectName("submarca")
        salir = QPushButton("Cerrar sesión")
        salir.clicked.connect(self.cerrar_sesion)
        capa.addWidget(self.nombre)
        capa.addWidget(self.rol)
        capa.addWidget(salir)
        self._mostrar_usuario()
        return lateral

    def _mostrar_usuario(self):
        usuario = self.cliente.usuario or {}
        self.nombre.setText(usuario.get("full_name") or usuario.get("username") or "")
        self.rol.setText(", ".join(NOMBRES_ROL.get(r, r) for r in self.cliente.roles()))

    def _barra_estado(self):
        barra = self.statusBar()
        self.conexion = QLabel("● Revisando servicios…")
        self.cola = QLabel("")
        self.boton_avisos = QPushButton("Avisos")
        self.boton_avisos.clicked.connect(self.abrir_avisos)
        barra.addWidget(self.conexion)
        barra.addWidget(self.cola)
        barra.addWidget(self.boton_avisos)
        barra.addPermanentWidget(QLabel(AVISO_PIE))

    def ir(self, indice):
        self.grupo.button(indice).setChecked(True)
        self.pila.setCurrentIndex(indice)
        self.pila.currentWidget().al_mostrar()

    def es_admin(self):
        return "ADMINISTRADOR" in self.cliente.roles()

    def accion(self, texto):
        bitacora.accion(self.cliente.nombre_usuario(), texto)

    def lanzar_corridas(self, version):
        self.ir(1)
        self.simulaciones.preseleccionar(version)

    def comparar(self, versiones):
        self.ir(2)
        self.comparacion.agregar(versiones)

    def revisar_salud(self):
        en_hilo(servicios.salud, self.cliente, listo=self._salud, fallo=self._sin_directorio)

    def _salud(self, datos):
        r = datos.get("resumen") or {}
        caidos = [s["nombre"] for s in datos.get("servicios") or [] if s.get("estado") == "caido"]
        color = "#22C55E" if not caidos and not r.get("degradado") else "#F59E0B"
        texto = "Conectado · %s ok" % r.get("ok", 0)
        if r.get("degradado"):
            texto += " · %s degradados" % r["degradado"]
        if caidos:
            texto += " · caídos: %s" % ", ".join(caidos)
        self.conexion.setText('<span style="color:%s">●</span> %s' % (color, texto))

    def _sin_directorio(self, exc):
        self.conexion.setText('<span style="color:#EF4444">●</span> Sin conexión: %s' % exc)

    def mostrar_cola(self, corridas):
        ejecutando = sum(1 for c in corridas if c["status"] == "ejecutando")
        espera = sum(1 for c in corridas if c["status"] == "encolado")
        self.cola.setText("Cola: %d ejecutando · %d en espera" % (ejecutando, espera))

    def revisar_sesion(self):
        en_hilo(servicios.sesion_actual, self.cliente, fallo=self._sesion_fallo)

    def _sesion_fallo(self, exc):
        if isinstance(exc, api.SesionCerrada):
            self.mostrar_error(exc)

    def revisar_avisos(self):
        en_hilo(servicios.avisos, self.cliente, listo=self._avisos, fallo=lambda exc: None)

    def _avisos(self, datos):
        pendientes = datos.get("no_leidas") or 0
        self.boton_avisos.setText("Avisos (%d)" % pendientes if pendientes else "Avisos")

    def abrir_avisos(self):
        DialogoAvisos(self).exec()
        self.revisar_avisos()

    def mostrar_error(self, exc):
        if isinstance(exc, api.SesionCerrada):
            self.reingresar(str(exc))
            return
        bitacora.error(str(exc))
        detalle = "\n".join("%s: %s" % (e.get("ruta"), e.get("mensaje")) if isinstance(e, dict) else str(e)
                            for e in getattr(exc, "errores", [])[:10])
        caja = QMessageBox(QMessageBox.Warning, "EPIDEMIA", str(exc), parent=self)
        if detalle:
            caja.setDetailedText(detalle)
        caja.exec()

    def reingresar(self, motivo):
        if self.reingresando:
            return
        self.reingresando = True
        for t in self.temporizadores:
            t.stop()
        dialogo = DialogoLogin(self.cliente, motivo or "La sesión terminó. Vuelve a iniciar sesión.")
        if dialogo.exec():
            for t in self.temporizadores:
                t.start()
            self.reingresando = False
            self._mostrar_usuario()
            self.pila.currentWidget().al_mostrar()
        else:
            self.close()

    def cerrar_sesion(self):
        self.cliente.cerrar_sesion()
        self.reingresar("Cerraste sesión.")

    def closeEvent(self, evento):
        self.cliente.cerrar_sesion()
        super().closeEvent(evento)
