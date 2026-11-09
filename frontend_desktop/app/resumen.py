import statistics

# D8 (propuesta): por escenario, media, mediana y percentiles 5 y 95 de sus réplicas.
INDICADORES = (("fallecimientos", "Muertes"), ("pico_casos_activos", "Pico de casos activos"),
               ("dia_pico", "Día del pico"), ("tasa_ataque", "Tasa de ataque"))
METRICAS = (("fallecimientos", "Muertes"), ("pico_casos_activos", "Pico de casos activos"))


def una_por_semilla(corridas):
    por_semilla = {}
    for corrida in sorted(corridas, key=lambda x: x["id"]):
        por_semilla[corrida["seed"]] = corrida
    return por_semilla


def semillas_comunes(grupos):
    if not grupos:
        return []
    return sorted(set.intersection(*(set(g) for g in grupos.values())))


def estadisticas(valores):
    valores = sorted(v for v in valores if v is not None)
    if not valores:
        return None
    if len(valores) == 1:
        p5 = p95 = valores[0]
    else:
        cortes = statistics.quantiles(valores, n=20, method="inclusive")
        p5, p95 = cortes[0], cortes[-1]
    return {"n": len(valores), "media": statistics.fmean(valores),
            "mediana": statistics.median(valores), "p5": p5, "p95": p95}


def curva(series, campo="casos_activos"):
    dias = min(len(s) for s in series)
    salida = []
    for i in range(dias):
        e = estadisticas([s[i][campo] for s in series])
        salida.append({"dia": series[0][i]["dia"], "mediana": e["mediana"], "p5": e["p5"], "p95": e["p95"]})
    return salida


def marcar_frontera(escenarios):
    for a in escenarios:
        if a["costo"] is None or a["impacto"] is None:
            a["dominado_por"] = None
            continue
        a["dominado_por"] = [
            b["nombre"] for b in escenarios
            if b is not a and b["costo"] is not None and b["impacto"] is not None
            and b["costo"] <= a["costo"] and b["impacto"]["mediana"] <= a["impacto"]["mediana"]
            and (b["costo"] < a["costo"] or b["impacto"]["mediana"] < a["impacto"]["mediana"])]
    return escenarios


def armar(elegidas, comparadas, datos_pareto, metrica, aviso):
    por_id = {x["id"]: x for x in comparadas}
    costos = {f["id"]: f.get("costo") for f in datos_pareto.get("filas") or []}
    escenarios = []
    for vid, corridas in elegidas.items():
        primera = corridas[0]
        datos = [por_id[x["id"]] for x in corridas if x["id"] in por_id]
        costo = estadisticas([costos.get(x["id"]) for x in corridas])
        escenarios.append({
            "version_id": vid,
            "nombre": "%s · v%s" % (primera["scenario_name"], primera["version_number"]),
            "corridas": [x["id"] for x in corridas],
            "n": len(datos),
            "indicadores": {clave: estadisticas([d.get(clave) for d in datos]) for clave, _ in INDICADORES},
            "impacto": estadisticas([d.get(metrica) for d in datos]),
            "costo": costo["mediana"] if costo else None,
            "curva": curva([d["serie"] for d in datos]) if datos else [],
        })
    return {"aviso": aviso or datos_pareto.get("aviso", ""), "metrica": metrica,
            "semillas": sorted(x["seed"] for x in next(iter(elegidas.values()))),
            "modelo_costo": datos_pareto.get("modelo_costo"),
            "trazabilidad_costos": datos_pareto.get("trazabilidad_costos") or [],
            "avisos": datos_pareto.get("avisos") or [],
            "escenarios": marcar_frontera(escenarios)}
