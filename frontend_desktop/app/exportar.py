import csv
from datetime import datetime
from html import escape
from pathlib import Path

from . import resumen


def guardar_csv(ruta, encabezados, filas):
    with open(ruta, "w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(encabezados)
        escritor.writerows(filas)


def texto_frontera(escenario):
    if escenario["dominado_por"] is None:
        return "Sin costo"
    if escenario["dominado_por"]:
        return "Dominado por " + ", ".join(escenario["dominado_por"])
    return "No dominado"


def tabla_comparacion(datos):
    encabezados = ["escenario", "replicas"]
    for clave, _ in resumen.INDICADORES:
        encabezados += [clave + "_media", clave + "_mediana", clave + "_p5", clave + "_p95"]
    encabezados += ["costo", "frontera"]
    filas = []
    for e in datos["escenarios"]:
        fila = [e["nombre"], e["n"]]
        for clave, _ in resumen.INDICADORES:
            s = e["indicadores"][clave] or {}
            fila += [s.get("media"), s.get("mediana"), s.get("p5"), s.get("p95")]
        filas.append(fila + [e["costo"], texto_frontera(e)])
    return encabezados, filas


def tabla_curvas(datos):
    encabezados = ["dia"]
    for e in datos["escenarios"]:
        encabezados += ["%s %s" % (e["nombre"], s) for s in ("mediana", "p5", "p95")]
    dias = min(len(e["curva"]) for e in datos["escenarios"])
    filas = []
    for i in range(dias):
        fila = [datos["escenarios"][0]["curva"][i]["dia"]]
        for e in datos["escenarios"]:
            punto = e["curva"][i]
            fila += [punto["mediana"], punto["p5"], punto["p95"]]
        filas.append(fila)
    return encabezados, filas


def csv_comparacion(ruta, datos):
    ruta = Path(ruta)
    curvas = ruta.with_name(ruta.stem + "_curvas.csv")
    guardar_csv(ruta, *tabla_comparacion(datos))
    guardar_csv(curvas, *tabla_curvas(datos))
    return ruta, curvas


def _rango(s, decimales=0, pct=False):
    if not s:
        return "—"
    f = (lambda x: "{:.{}f}%".format(x * 100, decimales)) if pct else (lambda x: "{:,.{}f}".format(x, decimales))
    return "%s (%s–%s), media %s" % (f(s["mediana"]), f(s["p5"]), f(s["p95"]), f(s["media"]))


def reporte_html(datos, usuario, imagenes):
    filas = []
    for e in datos["escenarios"]:
        ind = e["indicadores"]
        filas.append("<tr><td>%s</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            escape(e["nombre"]), e["n"], _rango(ind["fallecimientos"]), _rango(ind["pico_casos_activos"]),
            _rango(ind["dia_pico"]), _rango(ind["tasa_ataque"], 1, pct=True),
            "—" if e["costo"] is None else "{:,.0f}".format(e["costo"]), escape(texto_frontera(e))))
    costos = "".join("<li>%s: %s %s (%s, %s)</li>" % (
        escape(str(c.get("tipo"))), c.get("valor"), escape(str(c.get("unidad"))),
        escape(str(c.get("fuente") or "sin fuente")), escape(str(c.get("estado"))))
        for c in datos["trazabilidad_costos"])
    graficas = "".join('<p><img src="%s" width="640"></p>' % nombre for nombre in imagenes)
    semillas = datos["semillas"]
    return """<html><body style="font-family: sans-serif; font-size: 10pt;">
<h2>Comparación de escenarios</h2>
<p>Generado el %s por %s · %d escenarios · %d réplicas por escenario (semillas %s a %s).</p>
<p style="background:#FEF9C3; padding:6px;"><b>Aviso:</b> %s</p>
%s
<h3>Indicadores por escenario</h3>
<p>Mediana (p5–p95) y media de las réplicas. La frontera se calcula sobre las medianas de %s y el costo
(D8, propuesta).</p>
<table border="1" cellspacing="0" cellpadding="4">
<tr><th>Escenario</th><th>Réplicas</th><th>Muertes</th><th>Pico de casos activos</th><th>Día del pico</th>
<th>Tasa de ataque</th><th>Costo</th><th>Frontera</th></tr>
%s
</table>
<h3>Supuestos</h3>
<p>Modelo de costo: %s</p>
<ul>%s</ul>
<p>Elegir entre los escenarios de la frontera es una decisión humana; este reporte no recomienda ninguno.</p>
</body></html>""" % (datetime.now().strftime("%Y-%m-%d %H:%M"), escape(usuario or ""), len(datos["escenarios"]),
                      len(semillas), semillas[0], semillas[-1], escape(datos["aviso"] or ""), graficas,
                      escape(dict(resumen.METRICAS).get(datos["metrica"], datos["metrica"]).lower()),
                      "\n".join(filas), escape(datos.get("modelo_costo") or "—"), costos or "<li>—</li>")


def documento(html, imagenes):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextDocument
    doc = QTextDocument()
    for nombre, imagen in imagenes.items():
        doc.addResource(QTextDocument.ImageResource, QUrl(nombre), imagen)
    doc.setHtml(html)
    return doc


def guardar_pdf(ruta, html, imagenes):
    from PySide6.QtGui import QPageSize, QPdfWriter
    escritor = QPdfWriter(str(ruta))
    escritor.setPageSize(QPageSize(QPageSize.A4))
    escritor.setResolution(96)
    documento(html, imagenes).print_(escritor)
