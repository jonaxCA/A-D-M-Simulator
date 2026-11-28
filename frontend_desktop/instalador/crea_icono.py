"""Dibuja icono.ico (la «E» de EPIDEMIA con los colores de estilo.qss) para el .exe.

    python frontend_desktop/instalador/crea_icono.py
"""
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter

TAMANOS = (16, 24, 32, 48, 64, 128, 256)


def dibuja(lado):
    imagen = QImage(lado, lado, QImage.Format_ARGB32)
    imagen.fill(Qt.transparent)
    p = QPainter(imagen)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#0F172A"))
    p.drawRoundedRect(QRectF(0, 0, lado, lado), lado * 0.22, lado * 0.22)
    p.setBrush(QColor("#3B82F6"))
    p.drawRect(QRectF(lado * 0.18, lado * 0.78, lado * 0.64, lado * 0.06))
    fuente = QFont("Segoe UI", 1, QFont.Bold)
    fuente.setPixelSize(int(lado * 0.62))
    p.setFont(fuente)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(QRectF(0, -lado * 0.04, lado, lado), Qt.AlignCenter, "E")
    p.end()
    return imagen


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    destino = Path(__file__).resolve().parent / "icono.ico"
    # Qt escribe un .ico de un solo tamaño: el de 256 px, que Windows reduce para los demás.
    dibuja(256).save(str(destino), "ICO")
    print(destino)
