from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

TONOS = {"gris": ("#334155", "#E2E8F0"), "azul": ("#1D4ED8", "#DBEAFE"), "verde": ("#15803D", "#DCFCE7"),
         "rojo": ("#B91C1C", "#FEE2E2"), "ambar": ("#A16207", "#FEF3C7")}
ESTADOS = {"borrador": ("Borrador", "gris"), "en_revision": ("En revisión", "azul"),
           "aprobado": ("Aprobado", "verde"), "rechazado": ("Rechazado", "rojo"),
           "encolado": ("En espera", "gris"), "ejecutando": ("Ejecutando", "azul"),
           "completado": ("Completada", "verde"), "fallido": ("Error", "rojo"),
           "cancelado": ("Cancelada", "ambar"), "publicado": ("Publicado", "verde"),
           "archivado": ("Archivado", "gris")}
NOMBRES_ROL = {"ANALISTA": "Analista", "ADMINISTRADOR": "Administrador",
               "EPIDEMIOLOGO": "Epidemiólogo", "CAPTURISTA": "Capturista"}


def estado(clave):
    return ESTADOS.get(clave, (clave or "—", "gris"))


def pastilla(clave, texto=None):
    nombre, tono = estado(clave) if texto is None else (texto, clave)
    etiqueta = QLabel(nombre)
    etiqueta.setObjectName("pastilla")
    etiqueta.setProperty("tono", tono)
    return etiqueta


def celda(texto, clave_estado=None, alinear_derecha=False, dato=None):
    item = QTableWidgetItem("—" if texto is None else str(texto))
    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    if clave_estado:
        frente, fondo = TONOS[estado(clave_estado)[1]]
        item.setForeground(QBrush(QColor(frente)))
        item.setBackground(QBrush(QColor(fondo)))
    if alinear_derecha:
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if dato is not None:
        item.setData(Qt.UserRole, dato)
    return item


def tabla(columnas, estirar=(0,)):
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setShowGrid(False)
    t.setAlternatingRowColors(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    for columna in estirar:
        t.horizontalHeader().setSectionResizeMode(columna, QHeaderView.Stretch)
    t.horizontalHeader().setHighlightSections(False)
    return t


def tarjeta(titulo=None):
    marco = QFrame()
    marco.setObjectName("tarjeta")
    capa = QVBoxLayout(marco)
    capa.setContentsMargins(14, 12, 14, 12)
    if titulo:
        etiqueta = QLabel(titulo)
        etiqueta.setObjectName("tituloTarjeta")
        capa.addWidget(etiqueta)
    return marco, capa


def encabezado(seccion, titulo, botones=()):
    marco = QFrame()
    marco.setObjectName("encabezado")
    capa = QHBoxLayout(marco)
    capa.setContentsMargins(20, 10, 20, 10)
    textos = QVBoxLayout()
    textos.setSpacing(0)
    miga = QLabel(seccion)
    miga.setObjectName("miga")
    nombre = QLabel(titulo)
    nombre.setObjectName("titulo")
    nombre.setWordWrap(True)
    textos.addWidget(miga)
    textos.addWidget(nombre)
    capa.addLayout(textos, 1)
    for boton in botones:
        capa.addWidget(boton)
    return marco, nombre


def dato_vertical(etiqueta, valor=""):
    caja = QWidget()
    capa = QVBoxLayout(caja)
    capa.setContentsMargins(0, 0, 0, 0)
    capa.setSpacing(2)
    arriba = QLabel(etiqueta)
    arriba.setObjectName("etiquetaDato")
    abajo = QLabel(valor)
    abajo.setObjectName("valorDato")
    abajo.setWordWrap(True)
    capa.addWidget(arriba)
    capa.addWidget(abajo)
    return caja, abajo


def num(valor, decimales=0):
    if valor is None or valor == "":
        return "—"
    return "{:,.{}f}".format(float(valor), decimales)


def pct(valor, decimales=0):
    return "—" if valor is None else "{:.{}f}%".format(float(valor) * 100, decimales)


def fecha(iso):
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


def sim(corrida_id):
    return "SIM-%04d" % corrida_id


def limpiar(capa):
    while capa.count():
        item = capa.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            limpiar(item.layout())
