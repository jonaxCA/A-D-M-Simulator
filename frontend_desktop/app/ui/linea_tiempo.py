from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

ALTO_FILA = 40
ALTO_REGLA = 26
ANCHO_NOMBRE = 190
OSCURO = QColor("#334155")
ACENTO = QColor("#3B82F6")
LINEA = QColor("#E2E8F0")
TEXTO = QColor("#0F172A")
TENUE = QColor("#64748B")


def _resumen(intervencion):
    params = intervencion.get("params") or {}
    valor = next((v for v in params.values() if isinstance(v, (int, float))), None)
    fin = intervencion.get("end_day")
    texto = "Días %s–%s" % (intervencion["start_day"], "fin" if fin is None else fin)
    if valor is not None and valor <= 1:
        texto += " · %d%%" % round(valor * 100)
    return texto


class LineaTiempo(QWidget):
    seleccion = Signal(int)

    def __init__(self):
        super().__init__()
        self.intervenciones = []
        self.horizonte = 120
        self.elegida = -1

    def poner(self, intervenciones, horizonte):
        self.intervenciones = intervenciones
        self.horizonte = max(horizonte or 1, 1)
        self.elegida = -1
        self.setMinimumHeight(ALTO_REGLA + max(len(intervenciones), 1) * ALTO_FILA + 4)
        self.update()

    def _x(self, dia):
        return ANCHO_NOMBRE + (self.width() - ANCHO_NOMBRE - 8) * dia / self.horizonte

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        ancho_dia = (self.width() - ANCHO_NOMBRE - 8) / self.horizonte
        paso = next((p for p in (5, 10, 20, 30, 50, 100, 200) if p * ancho_dia >= 34), 365)
        p.setPen(TENUE)
        p.drawText(8, 18, "Día de simulación")
        for dia in range(0, self.horizonte + 1, paso):
            x = self._x(dia)
            p.setPen(LINEA)
            p.drawLine(int(x), ALTO_REGLA, int(x), self.height())
            if x + 28 < self.width():
                p.setPen(TENUE)
                p.drawText(int(x) + 2, 18, str(dia))
        if not self.intervenciones:
            p.setPen(TENUE)
            p.drawText(ANCHO_NOMBRE, ALTO_REGLA + 24, "Sin intervenciones: es el escenario base.")
        for i, iv in enumerate(self.intervenciones):
            y = ALTO_REGLA + i * ALTO_FILA
            p.setPen(LINEA)
            p.drawLine(0, y, self.width(), y)
            p.setPen(TEXTO)
            p.drawText(8, y + 17, iv.get("name") or iv["code"])
            p.setPen(TENUE)
            p.drawText(8, y + 32, "Capa %s" % (iv.get("target_layer") or "—"))
            inicio = self._x(iv["start_day"])
            fin = self._x(self.horizonte if iv.get("end_day") is None else iv["end_day"])
            caja = QRectF(inicio, y + 8, max(fin - inicio, 4), ALTO_FILA - 16)
            p.setPen(Qt.NoPen)
            p.setBrush(ACENTO if i == self.elegida else OSCURO)
            p.drawRect(caja)
            texto = _resumen(iv)
            if p.fontMetrics().horizontalAdvance(texto) + 12 <= caja.width():
                p.setPen(QPen(QColor("#FFFFFF")))
                p.drawText(caja.adjusted(6, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, texto)
            else:
                p.setPen(TEXTO)
                p.drawText(QRectF(caja.right() + 6, caja.top(), self.width(), caja.height()),
                           Qt.AlignVCenter | Qt.AlignLeft, texto)
        p.end()

    def mousePressEvent(self, evento):
        fila = int((evento.position().y() - ALTO_REGLA) // ALTO_FILA)
        if 0 <= fila < len(self.intervenciones):
            self.elegida = fila
            self.update()
            self.seleccion.emit(fila)
