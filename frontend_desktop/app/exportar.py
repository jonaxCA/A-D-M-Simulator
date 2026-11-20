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
        return "Sin personas-día"
    if escenario["dominado_por"]:
        return "Dominado por " + ", ".join(escenario["dominado_por"])
    return "No dominado"


def tabla_comparacion(datos):
    encabezados = ["escenario", "replicas"]
    for clave, _ in resumen.INDICADORES:
        encabezados += [clave + "_media", clave + "_mediana", clave + "_p5", clave + "_p95"]
    encabezados += ["personas_dia", "costo_pesos_mxn", "frontera"]
    filas = []
    for e in datos["escenarios"]:
        fila = [e["nombre"], e["n"]]
        for clave, _ in resumen.INDICADORES:
            s = e["indicadores"][clave] or {}
            fila += [s.get("media"), s.get("mediana"), s.get("p5"), s.get("p95")]
        filas.append(fila + [e["costo"], e.get("costo_pesos") if e.get("costo_pesos") is not None
                                  else "Sin dato", texto_frontera(e)])
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


def reporte_corrida(resultado, motor):
    corrida = resultado["corrida"]
    filas = (
        ("Escenario", corrida.get("scenario_name")), ("Versión del escenario", corrida.get("version_number")),
        ("Región", corrida.get("region_name")), ("Enfermedad", corrida.get("disease_name")),
        ("Motor", motor), ("Versión del motor", resultado.get("engine_version")),
        ("Semilla", corrida.get("seed")), ("Población simulada (agentes)", corrida.get("population_size")),
        ("Horizonte (días)", corrida.get("horizon_days")), ("Finalizada (ISO 8601)", corrida.get("finished_at")),
        ("Huella del escenario", resultado.get("scenario_checksum")),
    )
    detalle = "".join("<tr><th>%s</th><td>%s</td></tr>" % (campo, _dato(valor)) for campo, valor in filas)
    trazas = resultado.get("trazabilidad") or []
    parametros = "".join(
        "<tr>%s</tr>" % "".join("<td>%s</td>" % _dato(t.get(k)) for k in ("parametro", "valor", "fuente", "estado"))
        for t in trazas
    ) or '<tr><td colspan="4">El servicio no informó parámetros.</td></tr>'
    indicadores = resultado.get("resumen") or {}
    metricas = "".join("<tr><th>%s</th><td>%s</td></tr>" % (
        nombre, _dato("{:.1%}".format(indicadores[clave]) if clave == "tasa_ataque"
                     and indicadores.get(clave) is not None else indicadores.get(clave))
    ) for clave, nombre in resumen.INDICADORES)
    categoria = (resultado.get("categoria") or {}).get("texto")
    limites = "".join("<li>%s</li>" % _dato(texto) for texto in resultado.get("simplificaciones") or [])
    return """<html><body>
<h2>Ficha de la corrida SIM-%04d</h2>
<p>%s</p><p>%s</p>
<table cellspacing="0" cellpadding="4">%s</table>
<h3>Indicadores de la corrida</h3>
<table cellspacing="0" cellpadding="4">%s</table>
<h3>Parámetros de la corrida</h3>
<table border="1" cellspacing="0" cellpadding="4">
<thead><tr><th>Parámetro</th><th>Valor</th><th>Fuente</th><th>Estado</th></tr></thead>%s</table>
<h3>Limitaciones del motor</h3><ul>%s</ul>
<p>Fuente: resultado guardado por el servicio <b>resultados</b>.</p>
</body></html>""" % (corrida["id"], _dato(resultado.get("aviso")), _dato(categoria), detalle, metricas, parametros,
                      limites or "<li>El servicio no informó limitaciones.</li>")


def _dato(valor):
    return "Sin dato" if valor is None or valor == "" else escape(str(valor))


def reporte_html(datos, usuario, imagenes):
    filas = []
    for e in datos["escenarios"]:
        ind = e["indicadores"]
        filas.append("<tr><td>%s</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            escape(e["nombre"]), e["n"], _rango(ind["fallecimientos"]), _rango(ind["pico_casos_activos"]),
            _rango(ind["dia_pico"]), _rango(ind["tasa_ataque"], 1, pct=True),
            "—" if e["costo"] is None else "{:,.0f}".format(e["costo"]),
            "Sin dato" if e.get("costo_pesos") is None else "${:,.2f}".format(e["costo_pesos"]),
            escape(texto_frontera(e))))
    costos = "".join("<li>%s: %s %s (%s, %s)</li>" % (
        escape(str(c.get("tipo"))), c.get("valor"), escape(str(c.get("unidad"))),
        escape(str(c.get("fuente") or "sin fuente")), escape(str(c.get("estado"))))
        for c in datos["trazabilidad_costos"])
    bandas = resumen.avisos_bandas(datos["escenarios"])
    advertencia = ""
    if bandas:
        mensajes = "; ".join(escape(x) for x in bandas)
        advertencia = (
            '<p style="background:#FEF3C7; padding:6px;">'
            '<b>Advertencia p5–p95:</b> %s '
            'La superposición no demuestra equivalencia.</p>' % mensajes
        )

    titulos = {"frontera.png": "Frontera de eficiencia", "curvas.png": "Casos activos por escenario"}
    celdas = "".join(
        '<td width="50%%" valign="top" align="center"><b>%s</b><br><img src="%s" width="420"></td>'
        % (titulos.get(nombre, ""), escape(nombre, quote=True))
        for nombre in imagenes[:2]
    )
    graficas = advertencia
    if celdas:
        graficas += (
            '<table border="0" cellpadding="2" cellspacing="0" '
            'width="100%%"><tr>%s</tr></table>' % celdas
        )
    graficas += "".join(
        '<p><img src="%s" width="300"></p>' % escape(nombre, quote=True)
        for nombre in imagenes[2:]
    )
    graficas += "<p>Fuentes: comparación (series e indicadores) y Pareto (costos). %s</p>" % escape(
        resumen.fuentes_graficas(datos["escenarios"]))
    corridas = "".join(
        "<li>%s: %s</li>" % (escape(e["nombre"]), ", ".join(
            "SIM-%04d (semilla %s)" % (r["id"], _dato(r.get("seed"))) for r in e.get("replicas", [])))
        for e in datos["escenarios"] if e.get("replicas")
    )
    referencias = ("<h3>Corridas de origen</h3><ul>%s</ul>"
                   "<p>La ficha PDF de cada corrida contiene la versión del motor y los parámetros guardados.</p>"
                   % corridas) if corridas else ""
    semillas = datos["semillas"]
    return """<html><body style="font-family: sans-serif; font-size: 10pt;">
<h2>Comparación de escenarios</h2>
<p>Generado el %s por %s · %d escenarios · %d réplicas por escenario (semillas %s a %s).</p>
<p style="background:#FEF9C3; padding:6px;"><b>Aviso:</b> %s</p>
%s
<h3 style="page-break-before: always;">Indicadores por escenario</h3>
<p>Mediana (p5–p95) y media de las réplicas. La frontera compara medianas de %s y personas-día (D3/D8); los pesos se muestran aparte.</p>
<table border="1" cellspacing="0" cellpadding="4">
<tr><th>Escenario</th><th>Réplicas</th><th>Muertes</th><th>Pico de casos activos</th><th>Día del pico</th>
<th>Tasa de ataque</th><th>Personas-día</th><th>Costo (MXN)</th><th>Frontera</th></tr>
%s
</table>
<h3>Supuestos</h3>
<p>Modelo de personas-día y costos: %s</p>
<ul>%s</ul>
%s
<p>Elegir entre los escenarios de la frontera es una decisión humana; este reporte no recomienda ninguno.</p>
</body></html>""" % (datetime.now().strftime("%Y-%m-%d %H:%M"), escape(usuario or ""), len(datos["escenarios"]),
                      len(semillas), semillas[0], semillas[-1], escape(datos["aviso"] or ""), graficas,
                      escape(dict(resumen.METRICAS).get(datos["metrica"], datos["metrica"]).lower()),
                      "\n".join(filas), escape(datos.get("modelo_costo") or "—"), costos or "<li>—</li>",
                      referencias)


def documento(html, imagenes):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextDocument
    doc = QTextDocument()
    for nombre, imagen in imagenes.items():
        doc.addResource(QTextDocument.ImageResource, QUrl(nombre), imagen)
    doc.setHtml(html)
    return doc


def guardar_pdf(ruta, html, imagenes):
    from PySide6.QtCore import QIODevice, QSaveFile
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter

    archivo = QSaveFile(str(ruta))
    if not archivo.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(archivo.errorString())
    escritor = QPdfWriter(archivo)
    escritor.setPageSize(QPageSize(QPageSize.A4))
    escritor.setPageOrientation(QPageLayout.Orientation.Landscape)
    escritor.setResolution(96)
    documento(html, imagenes).print_(escritor)
    del escritor
    if not archivo.size():
        raise OSError("No se pudo generar el contenido del reporte.")
    if not archivo.commit():
        raise OSError(archivo.errorString())
