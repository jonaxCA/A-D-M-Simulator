from math import cos, radians

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


NIVELES = {
    "baja": ("Baja", "#15803D"), "moderada": ("Moderada", "#954809"),
    "alta": ("Alta", "#C2410C"), "muy_alta": ("Muy alta", "#B91C1C"),
    "critica": ("Crítica", "#86185E"), "sin dato": ("Sin dato", "#CBD5E1"),
}


class MapaMunicipal(QGraphicsView):
    municipio = Signal(str)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(300)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.poligonos = {}

    def poner(self, geometria, indicadores):
        self.scene().clear()
        self.poligonos.clear()
        escala_lon = cos(radians(25.5))
        por_codigo = {m["region_code"]: m for m in indicadores}
        for feature in geometria.get("features", []):
            propiedades = feature["properties"]
            codigo = propiedades["region_code"]
            forma = feature["geometry"]
            if forma["type"] == "Polygon":
                poligonos = [forma["coordinates"]]
            elif forma["type"] == "MultiPolygon":
                poligonos = forma["coordinates"]
            else:
                continue
            camino = QPainterPath()
            camino.setFillRule(Qt.OddEvenFill)
            for poligono in poligonos:
                for anillo in poligono:
                    if not anillo:
                        continue
                    lon, lat = anillo[0]
                    camino.moveTo(lon * escala_lon, -lat)
                    for lon, lat in anillo[1:]:
                        camino.lineTo(lon * escala_lon, -lat)
                    camino.closeSubpath()
            if camino.isEmpty():
                continue
            datos = por_codigo.get(codigo, {})
            nivel, color = NIVELES.get(datos.get("nivel"), NIVELES["sin dato"])
            item = self.scene().addPath(camino, self._borde(False), QBrush(QColor(color)))
            item.setData(0, codigo)
            item.setToolTip("%s · %s" % (propiedades["name"], nivel))
            self.poligonos[codigo] = item
        self.scene().setSceneRect(self.scene().itemsBoundingRect())
        self._ajustar()

    def _borde(self, seleccionado):
        lapiz = QPen(QColor("#0F172A" if seleccionado else "#FFFFFF"))
        lapiz.setCosmetic(True)
        lapiz.setWidth(2 if seleccionado else 1)
        return lapiz

    def _ajustar(self):
        if self.poligonos:
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._ajustar()

    def elegir(self, codigo):
        for clave, item in self.poligonos.items():
            item.setPen(self._borde(clave == codigo))
            item.setZValue(int(clave == codigo))

    def mousePressEvent(self, evento):
        item = self.itemAt(evento.position().toPoint())
        if item is not None and evento.button() == Qt.LeftButton:
            self.municipio.emit(item.data(0))
        super().mousePressEvent(evento)
