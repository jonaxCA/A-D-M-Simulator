"""Tema claro fijo para toda la app.

La app se diseñó en claro (disenios_figma/estilos.jpeg) y estilo.qss solo pinta algunos widgets.
Con Windows en modo oscuro, Qt 6 le pasa a la app la paleta oscura del sistema: lo que estilo.qss
no pinta (pestañas, áreas con desplazamiento, casillas, fechas, listas desplegables, divisores)
salía con fondo negro y el texto oscuro de estilo.qss encima. Aquí se fija el esquema claro y una
paleta con los colores de estilo.qss, así se ve igual en cualquier sistema.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

# Los mismos colores de estilo.qss.
FONDO = "#F1F5F9"
BLANCO = "#FFFFFF"
TEXTO = "#0F172A"
TENUE = "#94A3B8"
BORDE = "#CBD5E1"
AZUL = "#3B82F6"

_ROLES = {
    QPalette.Window: FONDO,
    QPalette.WindowText: TEXTO,
    QPalette.Base: BLANCO,
    QPalette.AlternateBase: "#F8FAFC",
    QPalette.Text: TEXTO,
    QPalette.Button: BLANCO,
    QPalette.ButtonText: TEXTO,
    QPalette.BrightText: BLANCO,
    QPalette.ToolTipBase: TEXTO,
    QPalette.ToolTipText: BLANCO,
    QPalette.PlaceholderText: TENUE,
    QPalette.Highlight: AZUL,
    QPalette.HighlightedText: BLANCO,
    QPalette.Link: "#1D4ED8",
    QPalette.LinkVisited: "#6D28D9",
    QPalette.Light: BLANCO,
    QPalette.Midlight: "#E2E8F0",
    QPalette.Mid: BORDE,
    QPalette.Dark: "#64748B",
    QPalette.Shadow: "#475569",
}
_DESHABILITADOS = (QPalette.WindowText, QPalette.Text, QPalette.ButtonText)


def paleta():
    p = QPalette()
    for rol, color in _ROLES.items():
        p.setColor(QPalette.All, rol, QColor(color))
    for rol in _DESHABILITADOS:
        p.setColor(QPalette.Disabled, rol, QColor(TENUE))
    return p


def aplicar(app):
    """Antes de setStyleSheet: fija el esquema claro (Qt 6.8 o más) y la paleta."""
    pistas = app.styleHints()
    if hasattr(pistas, "setColorScheme"):
        pistas.setColorScheme(Qt.ColorScheme.Light)
    app.setPalette(paleta())
