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
    curvas = []
    for e in datos["escenarios"]:
        encabezados += ["%s %s" % (e["nombre"], s) for s in ("mediana", "p5", "p95")]
        curvas.append({p["dia"]: p for p in e["curva"]})
    filas = []
    for dia in sorted({d for curva in curvas for d in curva}):
        fila = [dia]
        for curva in curvas:
            punto = curva.get(dia, {})
            fila += [punto.get(k) for k in ("mediana", "p5", "p95")]
        filas.append(fila)
    return encabezados, filas


def filas_diferencias(datos, referencia):
    escenarios = datos["escenarios"]
    base = escenarios[referencia]
    return [(e["nombre"], nombre, unidad,
             "{:+,.2f}".format(absolute) if absolute is not None else "Sin dato",
             "{:+.2%}".format(relativa) if relativa is not None else "No aplica")
            for i, e in enumerate(escenarios) if i != referencia
            for nombre, unidad, absolute, relativa in resumen.diferencias(base, e)]


def csv_comparacion(ruta, datos, referencia=None):
    ruta = Path(ruta)
    curvas = ruta.with_name(ruta.stem + "_curvas.csv")
    guardar_csv(ruta, *tabla_comparacion(datos))
    guardar_csv(curvas, *tabla_curvas(datos))
    if referencia is not None:
        diferencias = ruta.with_name(ruta.stem + "_diferencias.csv")
        base = datos["escenarios"][referencia]["nombre"]
        guardar_csv(diferencias, ["referencia", "escenario", "indicador", "unidad",
                                  "diferencia_absoluta", "diferencia_relativa"],
                    [(base,) + fila for fila in filas_diferencias(datos, referencia)])
        return ruta, curvas, diferencias
    return ruta, curvas


def _rango(s, decimales=0, pct=False):
    if not s:
        return "—"
    f = (lambda x: "{:.{}f}%".format(x * 100, decimales)) if pct else (lambda x: "{:,.{}f}".format(x, decimales))
    return "%s (%s–%s), media %s" % (f(s["mediana"]), f(s["p5"]), f(s["p95"]), f(s["media"]))


def reporte_corrida(resultado, motor, grafica=False):
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
    motivo = (resultado.get("categoria") or {}).get("motivo")
    limites = "".join("<li>%s</li>" % _dato(texto) for texto in resultado.get("simplificaciones") or [])
    serie = resultado.get("serie") or []
    serie_html = ""
    if grafica and serie:
        serie_html = ('<h3>Casos activos de la corrida</h3>'
                      '<p>Fuente: resultados · día %s a %s · %s (%s) · personas simuladas.</p>'
                      '<p><img src="serie_corrida.png" width="600"></p>'
                      % (serie[0]["dia"], serie[-1]["dia"], _dato(motor), _dato(resultado.get("engine_version"))))
    return """<html><body>
<h2>Ficha de la corrida SIM-%04d</h2>
<p>%s</p><p>%s</p><p>%s</p>
<table cellspacing="0" cellpadding="4">%s</table>
%s
<h3>Indicadores de la corrida</h3>
<table cellspacing="0" cellpadding="4">%s</table>
<h3>Parámetros de la corrida</h3>
<table border="1" cellspacing="0" cellpadding="4">
<thead><tr><th>Parámetro</th><th>Valor</th><th>Fuente</th><th>Estado</th></tr></thead>%s</table>
<h3>Metodología</h3>
<p>Indicadores y parámetros guardados de una corrida. El identificador SIM, la versión del escenario,
la semilla y la huella permiten rastrear el resultado. La fuente es el servicio resultados.</p>
<h3>Limitaciones del motor</h3><ul>%s</ul>
</body></html>""" % (corrida["id"], _dato(resultado.get("aviso")), _dato(categoria), _dato(motivo),
                      detalle, serie_html, metricas, parametros,
                      limites or "<li>El servicio no informó limitaciones.</li>")


def _dato(valor):
    return "Sin dato" if valor is None or valor == "" else escape(str(valor))


def reporte_html(datos, usuario, imagenes, referencia=None):
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
    graficas += ("<p>Fuentes: comparación (series e indicadores), corridas (motor) y Pareto (costos). %s "
                 "Unidades: días simulados, personas simuladas y personas-día.</p>"
                 % escape(resumen.fuentes_graficas(datos["escenarios"])))
    corridas = "".join(
        "<li>%s: %s</li>" % (escape(e["nombre"]), ", ".join(
            "SIM-%04d (semilla %s)%s" % (
                r["id"], _dato(r.get("seed")), " · " + _dato(r["engine_version"]) if r.get("engine_version") else "")
            for r in e.get("replicas", [])))
        for e in datos["escenarios"] if e.get("replicas")
    )
    referencias = ("<h3>Corridas de origen</h3><ul>%s</ul>"
                   "<p>La ficha PDF de cada corrida contiene la versión del motor y los parámetros guardados.</p>"
                   % corridas) if corridas else ""
    diferencias = ""
    if referencia is not None:
        base = datos["escenarios"][referencia]["nombre"]
        celdas = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % escape(v) for v in fila)
                         for fila in filas_diferencias(datos, referencia))
        diferencias = ("<h3>Diferencias entre medianas</h3><p>Referencia: <b>%s</b>. %s</p>"
                       '<table border="1" cellspacing="0" cellpadding="4"><thead><tr><th>Escenario</th>'
                       "<th>Indicador</th><th>Unidad</th><th>Absoluta</th><th>Relativa</th>"
                       "</tr></thead>%s</table>" % (escape(base), escape(resumen.METODO_DIFERENCIAS), celdas))
    modelos = resumen.modelos_corridas(datos["escenarios"])
    limitaciones = (" Las réplicas incluyen distintos motores o versiones; las diferencias son descriptivas."
                    if len(modelos) > 1 else "")
    if any(not resumen.trazable(e) for e in datos["escenarios"]):
        limitaciones += " Las gráficas omiten elementos sin motor, versión o periodo identificado."
    if len(resumen.horizontes_corridas(datos["escenarios"])) > 1:
        limitaciones += " Los indicadores incluyen distintos horizontes de simulación."
    semillas = datos["semillas"]
    return """<html><body style="font-family: sans-serif; font-size: 10pt;">
<h2>Comparación de escenarios</h2>
<p>Generado el %s por %s · %d escenarios · %d réplicas por escenario (semillas %s a %s).</p>
<p style="background:#FEF9C3; padding:6px;"><b>Aviso:</b> %s</p>
%s
<h3 style="page-break-before: always;">Indicadores por escenario</h3>
<p>Se usa una corrida completada por semilla, con semillas presentes en todos los escenarios.
La tabla muestra mediana, media e intervalo p5–p95 entre réplicas. Las curvas agregan los días compartidos.
La frontera compara medianas de %s y personas-día (D3/D8); los pesos se muestran aparte.%s</p>
<table border="1" cellspacing="0" cellpadding="4">
<tr><th>Escenario</th><th>Réplicas</th><th>Muertes</th><th>Pico de casos activos</th><th>Día del pico</th>
<th>Tasa de ataque</th><th>Personas-día</th><th>Costo (MXN)</th><th>Frontera</th></tr>
%s
</table>
%s
<h3>Supuestos</h3>
<p>Modelo de personas-día y costos: %s</p>
<ul>%s</ul>
%s
<p>Elegir entre los escenarios de la frontera es una decisión humana; este reporte no recomienda ninguno.</p>
</body></html>""" % (datetime.now().strftime("%Y-%m-%d %H:%M"), escape(usuario or ""), len(datos["escenarios"]),
                      len(semillas), semillas[0], semillas[-1], escape(datos["aviso"] or ""), graficas,
                      escape(dict(resumen.METRICAS).get(datos["metrica"], datos["metrica"]).lower()),
                      escape(limitaciones), "\n".join(filas), diferencias,
                      escape(datos.get("modelo_costo") or "—"), costos or "<li>—</li>",
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
