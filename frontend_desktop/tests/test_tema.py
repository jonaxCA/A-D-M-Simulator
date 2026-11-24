"""El tema claro fijo: con Windows en modo oscuro, Qt pasaba la paleta oscura y lo que estilo.qss no
pinta salía negro con letras negras (tema.py)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_desktop.app.ui import tema  # noqa: E402


def _luz(color):
    return color.lightness()


def test_la_paleta_es_clara_con_texto_oscuro():
    p = tema.paleta()
    for fondo in (QPalette.Window, QPalette.Base, QPalette.Button):
        assert _luz(p.color(fondo)) > 200
    for texto in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        assert _luz(p.color(texto)) < 60
    # El texto deshabilitado se distingue del normal, sin perderse en el fondo.
    assert 100 < _luz(p.color(QPalette.Disabled, QPalette.Text)) < 200


def test_aplicar_fija_la_paleta_y_el_esquema_claro():
    app = QApplication.instance() or QApplication([])
    tema.aplicar(app)
    assert app.palette().color(QPalette.Window) == tema.paleta().color(QPalette.Window)
    if hasattr(app.styleHints(), "setColorScheme"):
        assert app.styleHints().colorScheme() in (Qt.ColorScheme.Light, Qt.ColorScheme.Unknown)
