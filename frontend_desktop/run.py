import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from frontend_desktop.app import bitacora
from frontend_desktop.app.api import Cliente
from frontend_desktop.app.ui.login import DialogoLogin
from frontend_desktop.app.ui.ventana import Ventana


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("epidemia-escritorio")
    app.setFont(QFont(["Inter", "Segoe UI", "Noto Sans", "Sans Serif"], 10))
    app.setStyleSheet((Path(__file__).parent / "app" / "ui" / "estilo.qss").read_text(encoding="utf-8"))
    archivo = bitacora.configurar(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    print("Bitácora de actividad: %s" % archivo)
    cliente = Cliente()
    if not DialogoLogin(cliente).exec():
        return 0
    ventana = Ventana(cliente)
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
