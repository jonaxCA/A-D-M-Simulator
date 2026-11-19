from PySide6.QtCharts import QAreaSeries, QChart, QChartView, QLineSeries, QScatterSeries, QValueAxis
from PySide6.QtCore import QMargins, QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

COLORES = ["#64748B", "#2563EB", "#0F766E", "#9333EA", "#C2410C", "#DB2777", "#65A30D", "#0891B2"]


def color(i):
    return QColor(COLORES[i % len(COLORES)])


def vista():
    v = QChartView()
    v.setRenderHint(QPainter.Antialiasing)
    v.setMinimumHeight(300)
    return v


def _grafica(titulo_x, titulo_y):
    g = QChart()
    g.setMargins(QMargins(4, 4, 4, 4))
    g.legend().setAlignment(Qt.AlignBottom)
    eje_x, eje_y = QValueAxis(), QValueAxis()
    eje_x.setTitleText(titulo_x)
    eje_y.setTitleText(titulo_y)
    eje_x.setLabelFormat("%.0f")
    eje_y.setLabelFormat("%.0f")
    g.addAxis(eje_x, Qt.AlignBottom)
    g.addAxis(eje_y, Qt.AlignLeft)
    return g, eje_x, eje_y


def _agregar(g, serie, ejes, en_leyenda=True):
    g.addSeries(serie)
    for eje in ejes:
        serie.attachAxis(eje)
    if not en_leyenda:
        for marca in g.legend().markers(serie):
            marca.setVisible(False)


def _poner(v, grafica):
    v.setChart(grafica)
    v.grafica = grafica


def _rango(eje, valores, margen=0.05):
    if not valores:
        return
    bajo, alto = min(valores), max(valores)
    holgura = (alto - bajo) * margen or abs(alto) * margen or 1
    eje.setRange(0 if bajo >= 0 else bajo - holgura, alto + holgura)


def curvas(v, escenarios, elegido):
    g, eje_x, eje_y = _grafica("Día de simulación", "Casos activos")
    valores_x, valores_y = [], []
    for i, e in enumerate(escenarios):
        if i == elegido and e["curva"]:
            alto, bajo = QLineSeries(), QLineSeries()
            for p in e["curva"]:
                alto.append(p["dia"], p["p95"])
                bajo.append(p["dia"], p["p5"])
            banda = QAreaSeries(alto, bajo)
            # QAreaSeries no es dueña de sus líneas: sin padre, Python las libera y Qt se cae al pintar.
            alto.setParent(banda)
            bajo.setParent(banda)
            relleno = color(i)
            relleno.setAlpha(50)
            banda.setBrush(QBrush(relleno))
            banda.setPen(QPen(Qt.NoPen))
            _agregar(g, banda, (eje_x, eje_y), en_leyenda=False)
            valores_y += [p["p95"] for p in e["curva"]]
        linea = QLineSeries()
        linea.setName(e["nombre"])
        linea.setPen(QPen(color(i), 3 if i == elegido else 2))
        for p in e["curva"]:
            linea.append(p["dia"], p["mediana"])
            valores_x.append(p["dia"])
            valores_y.append(p["mediana"])
        _agregar(g, linea, (eje_x, eje_y))
    _rango(eje_x, valores_x, 0)
    _rango(eje_y, valores_y)
    _poner(v, g)


def _escala(maximo):
    for divisor, nombre in ((1e6, " (millones)"), (1e3, " (miles)")):
        if maximo >= divisor:
            return divisor, nombre
    return 1, ""


def frontera(v, escenarios, nombre_metrica):
    puntos = [(i, e) for i, e in enumerate(escenarios) if e["costo"] is not None and e["impacto"]]
    divisor, unidad = _escala(max([e["costo"] for _, e in puntos] or [0]))
    g, eje_x, eje_y = _grafica("Costo%s, según el servicio pareto" % unidad, "%s (mediana)" % nombre_metrica)
    if not puntos:
        g.setTitle("Sin costos calculados: no hay frontera")
    eje_x.setLabelFormat("%.1f")
    en_frontera = sorted((e["costo"] / divisor, e["impacto"]["mediana"]) for _, e in puntos if not e["dominado_por"])
    if len(en_frontera) > 1:
        linea = QLineSeries()
        linea.setPen(QPen(QColor("#0F172A"), 1, Qt.DashLine))
        for x, y in en_frontera:
            linea.append(x, y)
        _agregar(g, linea, (eje_x, eje_y), en_leyenda=False)
    for i, e in puntos:
        barra = QLineSeries()
        barra.setPen(QPen(color(i), 2))
        barra.append(QPointF(e["costo"] / divisor, e["impacto"]["p5"]))
        barra.append(QPointF(e["costo"] / divisor, e["impacto"]["p95"]))
        _agregar(g, barra, (eje_x, eje_y), en_leyenda=False)
        punto = QScatterSeries()
        punto.setName(e["nombre"] + ("" if not e["dominado_por"] else " (dominado)"))
        punto.setMarkerSize(14)
        punto.setColor(color(i) if not e["dominado_por"] else QColor("#FFFFFF"))
        punto.setBorderColor(color(i))
        punto.append(e["costo"] / divisor, e["impacto"]["mediana"])
        _agregar(g, punto, (eje_x, eje_y))
    _rango(eje_x, [e["costo"] / divisor for _, e in puntos], 0.08)
    _rango(eje_y, [e["impacto"][k] for _, e in puntos for k in ("p5", "p95")])
    _poner(v, g)
