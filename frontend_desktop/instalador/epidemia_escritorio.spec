# -*- mode: python ; coding: utf-8 -*-
# Receta de PyInstaller para la app de escritorio: un solo EPIDEMIA-Escritorio.exe, sin consola.
#
#   pip install pyinstaller
#   pyinstaller --noconfirm --clean frontend_desktop/instalador/epidemia_escritorio.spec
#
# Deja el .exe en dist/. Incluye los XSD de docs/contratos (la app valida cada respuesta XML) y
# estilo.qss, en las mismas rutas relativas que usa el código.
from pathlib import Path

AQUI = Path(SPECPATH).resolve()
RAIZ = AQUI.parents[1]

datos = [(str(p), str(p.parent.relative_to(RAIZ))) for p in sorted((RAIZ / "docs" / "contratos").rglob("*.xsd"))]
datos.append((str(RAIZ / "frontend_desktop" / "app" / "ui" / "estilo.qss"), "frontend_desktop/app/ui"))

a = Analysis(
    [str(AQUI / "epidemia_escritorio.py")],
    pathex=[str(RAIZ)],
    datas=datos,
    hiddenimports=["frontend_desktop.run"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf",
              "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtBluetooth", "PySide6.QtLocation"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="EPIDEMIA-Escritorio",
    icon=str(AQUI / "icono.ico"),
    console=False,
    upx=False,
)
