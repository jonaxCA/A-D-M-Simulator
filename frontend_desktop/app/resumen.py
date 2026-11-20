import statistics

# D8 (propuesta): por escenario, media, mediana y percentiles 5 y 95 de sus réplicas.
INDICADORES = (("fallecimientos", "Muertes"), ("pico_casos_activos", "Pico de casos activos"),
               ("dia_pico", "Día del pico"), ("tasa_ataque", "Tasa de ataque"))
METRICAS = (("fallecimientos", "Muertes"), ("pico_casos_activos", "Pico de casos activos"))
UNIDADES = {"fallecimientos": "personas simuladas", "pico_casos_activos": "personas simuladas",
            "dia_pico": "días", "tasa_ataque": "puntos porcentuales"}
METODO_DIFERENCIAS = ("Diferencias entre medianas descriptivas. Absoluta: escenario menos referencia, con su signo. "
                      "Relativa: la resta dividida entre la mediana de referencia. Con referencia cero, no aplica.")


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
    por_dia = [{p["dia"]: p[campo] for p in s} for s in series]
    dias = sorted(set.intersection(*(set(s) for s in por_dia))) if por_dia else []
    salida = []
    for dia in dias:
        e = estadisticas([s[dia] for s in por_dia])
        salida.append({"dia": dia, "mediana": e["mediana"], "p5": e["p5"], "p95": e["p95"]})
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



def avisos_bandas(escenarios):
    """Detecta superposición de bandas p5-p95 del impacto."""
    avisos = []
    for i, primero in enumerate(escenarios):
        a = primero.get("impacto") or {}
        if a.get("p5") is None or a.get("p95") is None:
            continue
        for segundo in escenarios[i + 1:]:
            b = segundo.get("impacto") or {}
            if b.get("p5") is None or b.get("p95") is None:
                continue
            if max(a["p5"], b["p5"]) <= min(a["p95"], b["p95"]):
                avisos.append(
                    "Las bandas p5–p95 de %s y %s se enciman."
                    % (primero["nombre"], segundo["nombre"])
                )
    return avisos


def armar(elegidas, comparadas, datos_pareto, metrica, aviso):
    por_id = {x["id"]: x for x in comparadas}
    costos = {f["id"]: f.get("costo") for f in datos_pareto.get("filas") or []}
    pesos = {f["id"]: f.get("costo_pesos") for f in datos_pareto.get("filas") or []}
    escenarios = []
    for vid, corridas in elegidas.items():
        primera = corridas[0]
        datos = [por_id[x["id"]] for x in corridas if x["id"] in por_id]
        costo = estadisticas([costos.get(x["id"]) for x in corridas])
        valores_pesos = [pesos.get(x["id"]) for x in corridas]
        total_pesos = estadisticas(valores_pesos) if all(v is not None for v in valores_pesos) else None
        escenarios.append({
            "version_id": vid,
            "nombre": "%s · v%s" % (primera["scenario_name"], primera["version_number"]),
            "corridas": [x["id"] for x in corridas],
            "replicas": [x for x in corridas if x["id"] in por_id],
            "n": len(datos),
            "indicadores": {clave: estadisticas([d.get(clave) for d in datos]) for clave, _ in INDICADORES},
            "impacto": estadisticas([d.get(metrica) for d in datos]),
            "costo": costo["mediana"] if costo else None,
            "costo_pesos": total_pesos["mediana"] if total_pesos else None,
            "curva": curva([d["serie"] for d in datos]) if datos else [],
        })
    return {"aviso": aviso or datos_pareto.get("aviso", ""), "metrica": metrica,
            "semillas": sorted(x["seed"] for x in next(iter(elegidas.values()))),
            "modelo_costo": datos_pareto.get("modelo_costo"),
            "trazabilidad_costos": datos_pareto.get("trazabilidad_costos") or [],
            "avisos": datos_pareto.get("avisos") or [],
            "escenarios": marcar_frontera(escenarios)}


def diferencias(base, escenario):
    filas = []
    for clave, nombre in INDICADORES:
        inicial = base["indicadores"].get(clave)
        final = escenario["indicadores"].get(clave)
        a = inicial["mediana"] if inicial else None
        b = final["mediana"] if final else None
        filas.append((nombre, UNIDADES[clave], *_delta(a, b, 100 if clave == "tasa_ataque" else 1)))
    for clave, nombre, unidad in (("costo", "Costo de intervención", "personas-día"),
                                   ("costo_pesos", "Costo monetario", "MXN")):
        filas.append((nombre, unidad, *_delta(base.get(clave), escenario.get(clave), 1)))
    return filas


def _delta(a, b, escala):
    if a is None or b is None:
        return None, None
    diferencia = b - a
    return diferencia * escala, diferencia / a if a else None


def modelos_corridas(escenarios):
    return {(r.get("engine"), r.get("engine_version"))
            for e in escenarios for r in e.get("replicas", [])}


def trazable(escenario):
    modelos = modelos_corridas([escenario])
    periodo = escenario.get("curva") or all(r.get("horizon_days") for r in escenario.get("replicas", []))
    return bool(periodo and modelos) and all(motor and version for motor, version in modelos)


def horizontes_corridas(escenarios):
    return {r["horizon_days"] for e in escenarios for r in e.get("replicas", []) if r.get("horizon_days")}


def fuentes_graficas(escenarios):
    periodos = {(e["curva"][0]["dia"], e["curva"][-1]["dia"]) for e in escenarios if e["curva"]}
    motores = sorted("%s (%s)" % (motor or "motor sin dato", version or "versión sin dato")
                     for motor, version in modelos_corridas(escenarios))
    periodo = ", ".join("día %s a %s" % x for x in sorted(periodos)) or "sin serie"
    horizontes = horizontes_corridas(escenarios)
    horizonte = " Horizontes originales: %s días." % ", ".join(map(str, sorted(horizontes))) if horizontes else ""
    return "Periodo simulado: %s. Motores y versiones: %s.%s" % (periodo, ", ".join(motores) or "sin dato", horizonte)
