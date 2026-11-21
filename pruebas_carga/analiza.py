"""Resumen de una corrida de perfiles.py con escalones.py (F4): por escalón, por perfil, los
endpoints más lentos, la saturación, la recuperación y las metas de RNF-A.

    python pruebas_carga/analiza.py <carpeta de RESULTADOS>

Lee cronologia.csv y usuarios.csv (los escribe perfiles.py) y locust_stats.csv (--csv de Locust).
Toma los escalones de las mismas variables que escalones.py. Escribe <carpeta>/resumen.md y lo
imprime. Solo usa la biblioteca estándar.

Criterios (se escriben también en el resumen):
- Un escalón está saturado si los errores llegan al 1 %, si el p95 pasa de 2 veces el del primer
  escalón y de 500 ms, o si con más usuarios las peticiones por segundo crecen menos del 10 %.
- Se recupera cuando, después de bajar la carga, una ventana de 10 s vuelve a un p95 de no más de
  1.2 veces el del primer escalón y sin errores.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from escalones import ajustes  # noqa: E402

CALENTAMIENTO = 10  # s al inicio de cada escalón que no cuentan (los usuarios van llegando)
EVENTOS = ("CASOS", "CORRIDA")  # tipos que no son peticiones: casos guardados y corridas completas


def percentil(valores, p):
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, max(0, int(round(p / 100 * len(ordenados) + 0.5)) - 1))]


def lee(carpeta):
    with open(os.path.join(carpeta, "cronologia.csv"), newline="", encoding="utf-8") as f:
        filas = [dict(r, t=float(r["t"]), estado=int(r["estado"]), ms=int(r["ms"]),
                      bytes=int(r["bytes"]), excepcion=int(r["excepcion"])) for r in csv.DictReader(f)]
    with open(os.path.join(carpeta, "usuarios.csv"), newline="", encoding="utf-8") as f:
        usuarios = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
    stats = []
    ruta = os.path.join(carpeta, "locust_stats.csv")
    if os.path.exists(ruta):
        with open(ruta, newline="") as f:
            stats = list(csv.DictReader(f))
    return filas, usuarios, stats


def perfil(nombre):
    return nombre.replace("[429] ", "").replace("[409] ", "").split(":", 1)[0]


def resumen_de(filas):
    """Peticiones reales (sin eventos): total, errores, 429, media, p50, p95, p99."""
    reales = [f for f in filas if f["tipo"] not in EVENTOS]
    aceptadas = [f["ms"] for f in reales if not f["nombre"].startswith("[429]")]
    return {"total": len(reales), "errores": sum(f["excepcion"] for f in reales),
            "limitadas": sum(1 for f in reales if f["nombre"].startswith("[429]")),
            "media": round(sum(aceptadas) / len(aceptadas)) if aceptadas else None,
            "p50": percentil(aceptadas, 50), "p95": percentil(aceptadas, 95),
            "p99": percentil(aceptadas, 99)}


def ms(v):
    return "—" if v is None else "%d" % v


def analiza(carpeta, entorno=None):
    if entorno is None:
        # Los valores con que corrió la prueba (perfiles.py los guarda); si no, los del entorno.
        entorno = dict(os.environ)
        guardados = os.path.join(carpeta, "escalones.json")
        if os.path.exists(guardados):
            with open(guardados, encoding="utf-8") as f:
                entorno.update(json.load(f))
    a = ajustes(entorno)
    filas, usuarios, stats = lee(carpeta)
    t0 = usuarios[0]["t"] if usuarios else filas[0]["t"]
    escalones = max(1, a["maximo"] // a["paso"])
    subida = escalones * a["segundos_paso"]
    lineas = ["# Resumen de la prueba de carga por perfiles", "",
              "Escalones de %d usuarios cada %d s hasta %d; luego %d usuarios durante %d s. Los "
              "primeros %d s de cada escalón no cuentan." % (a["paso"], a["segundos_paso"], a["maximo"],
                                                            a["base"], a["recuperacion"], CALENTAMIENTO), ""]

    # --- Escalones ---------------------------------------------------------------------------
    tabla, base, saturado, capacidad = [], None, None, None
    for k in range(escalones):
        ini, fin = t0 + k * a["segundos_paso"] + CALENTAMIENTO, t0 + (k + 1) * a["segundos_paso"]
        en = [f for f in filas if ini <= f["t"] < fin]
        r = resumen_de(en)
        r.update(usuarios=a["paso"] * (k + 1), rps=round(r["total"] / (fin - ini), 1),
                 pct_errores=round(100 * r["errores"] / r["total"], 2) if r["total"] else 0.0,
                 casos_s=round(sum(f["bytes"] for f in en if f["tipo"] == "CASOS") / (fin - ini), 1))
        motivo = None
        if base is None:
            base = r
        elif r["total"]:
            if r["pct_errores"] >= 1:
                motivo = "errores ≥ 1 %"
            elif r["p95"] and base["p95"] and r["p95"] > 2 * base["p95"] and r["p95"] > 500:
                motivo = "p95 > 2× el inicial y > 500 ms"
            elif tabla and tabla[-1]["rps"] and r["rps"] < 1.1 * tabla[-1]["rps"]:
                motivo = "las peticiones por segundo dejan de crecer"
        r["motivo"] = motivo
        if motivo and saturado is None:
            saturado = r
        if saturado is None:
            capacidad = r
        tabla.append(r)

    lineas += ["## Por escalón", "",
               "| Usuarios | Peticiones/s | Casos/s | Media ms | p50 | p95 | p99 | Errores | 429 | Saturación |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    for r in tabla:
        lineas.append("| %d | %.1f | %.1f | %s | %s | %s | %s | %d (%.2f %%) | %d | %s |" % (
            r["usuarios"], r["rps"], r["casos_s"], ms(r["media"]), ms(r["p50"]), ms(r["p95"]),
            ms(r["p99"]), r["errores"], r["pct_errores"], r["limitadas"], r["motivo"] or ""))
    lineas.append("")
    if saturado:
        lineas.append("**Saturación:** a los %d usuarios (%s). El último escalón sano fue el de %d "
                      "usuarios, con %.1f peticiones por segundo y p95 de %s ms." % (
                          saturado["usuarios"], saturado["motivo"], capacidad["usuarios"] if capacidad else 0,
                          capacidad["rps"] if capacidad else 0, ms(capacidad["p95"]) if capacidad else "—"))
    else:
        lineas.append("**Saturación:** no se alcanzó hasta %d usuarios." % a["maximo"])
    lineas.append("")

    # --- Recuperación ------------------------------------------------------------------------
    caida = t0 + subida
    recuperado = None
    t = caida
    while t + 10 <= caida + a["recuperacion"]:
        r = resumen_de([f for f in filas if t <= f["t"] < t + 10])
        if r["total"] and r["errores"] == 0 and r["p95"] is not None and base and base["p95"] \
                and r["p95"] <= 1.2 * base["p95"]:
            recuperado = t + 10 - caida
            break
        t += 5
    if recuperado is not None:
        lineas.append("**Recuperación:** al bajar a %d usuarios, el p95 volvió a su nivel inicial en "
                      "%d s, sin errores." % (a["base"], recuperado))
    else:
        lineas.append("**Recuperación:** en %d s después de bajar a %d usuarios no volvió al p95 "
                      "inicial sin errores." % (a["recuperacion"], a["base"]))
    lineas.append("")

    # --- Por perfil --------------------------------------------------------------------------
    lineas += ["## Por perfil (toda la prueba)", "",
               "| Perfil | Peticiones | Errores | 429 | Media ms | p50 | p95 | p99 |", "|---|---|---|---|---|---|---|---|"]
    perfiles = sorted({perfil(f["nombre"]) for f in filas if f["tipo"] not in EVENTOS})
    for p in perfiles:
        r = resumen_de([f for f in filas if perfil(f["nombre"]) == p])
        lineas.append("| %s | %d | %d | %d | %s | %s | %s | %s |" % (
            p, r["total"], r["errores"], r["limitadas"], ms(r["media"]), ms(r["p50"]), ms(r["p95"]), ms(r["p99"])))
    lineas.append("")

    # --- Endpoints más lentos ----------------------------------------------------------------
    lentos = [s for s in stats if s.get("Name") != "Aggregated" and s.get("Type") not in EVENTOS
              and not s["Name"].startswith("[429]") and s.get("95%") not in (None, "", "N/A")]
    lentos.sort(key=lambda s: float(s["95%"]), reverse=True)
    lineas += ["## Los 10 endpoints más lentos (p95, toda la prueba)", "",
               "| Endpoint | Peticiones | Fallos | Media ms | p95 | p99 |", "|---|---|---|---|---|---|"]
    for s in lentos[:10]:
        lineas.append("| %s | %s | %s | %.0f | %s | %s |" % (
            s["Name"], s["Request Count"], s["Failure Count"], float(s["Average Response Time"]),
            s["95%"], s["99%"]))
    lineas.append("")

    # --- Metas de RNF-A ----------------------------------------------------------------------
    def p95_de(condicion, desde=None, hasta=None):
        v = [f["ms"] for f in filas if f["tipo"] not in EVENTOS and not f["nombre"].startswith("[")
             and condicion(f["nombre"]) and (desde is None or desde <= f["t"] < hasta)]
        return percentil(v, 95), len(v)

    sano = tabla.index(capacidad) if capacidad else 0
    desde, hasta = t0 + sano * a["segundos_paso"] + CALENTAMIENTO, t0 + (sano + 1) * a["segundos_paso"]
    api_get, n_api = p95_de(lambda n: " GET " in n and not n.startswith("web:"), desde, hasta)
    tablero, n_tab = p95_de(lambda n: n.startswith("web: GET / ") or n == "web: GET /dashboard")
    cien, n_cien = p95_de(lambda n: "(100 casos)" in n)
    lanza, n_lanza = p95_de(lambda n: n == "corridas: POST corridas /runs")
    casos_max = max((r["casos_s"] for r in tabla), default=0)
    web_sin_error = 0
    columnas = usuarios[0].keys() if usuarios else []
    if "ConsultaWeb" in columnas:
        for r, k in zip(tabla, range(len(tabla))):
            web = [f for f in filas if perfil(f["nombre"]) == "web"
                   and t0 + k * a["segundos_paso"] <= f["t"] < t0 + (k + 1) * a["segundos_paso"]]
            if web and not any(f["excepcion"] for f in web):
                en = [u["ConsultaWeb"] for u in usuarios
                      if t0 + k * a["segundos_paso"] <= u["t"] < t0 + (k + 1) * a["segundos_paso"]]
                web_sin_error = max([web_sin_error] + en)

    def cumple(valor, meta, menor=True):
        if valor is None:
            return "sin datos"
        return "cumple" if (valor <= meta if menor else valor >= meta) else "no cumple"

    lineas += ["## Metas de rendimiento (RNF-A)", "",
               "| Requisito | Meta | Medido | Resultado |", "|---|---|---|---|",
               "| RNF-A01 consultas de los servicios | p95 ≤ 500 ms | p95 %s ms en el último escalón sano (%d peticiones GET) | %s |"
               % (ms(api_get), n_api, cumple(api_get, 500)),
               "| RNF-A05 casos por `sincronizacion` | 100 casos/s | hasta %.1f casos/s en un escalón | %s |"
               % (casos_max, cumple(casos_max, 100, menor=False)),
               "| RNF-A06 personas en la web a la vez | 50 sin errores | hasta %d en la web sin errores | %s |"
               % (web_sin_error, cumple(web_sin_error, 50, menor=False)),
               "| RNF-A07 el tablero carga | ≤ 3 s | p95 %s ms (%d cargas) | %s |" % (ms(tablero), n_tab, cumple(tablero, 3000)),
               "| RNF-A08 lote de 100 casos | ≤ 30 s | p95 %s ms (%d lotes) | %s |" % (ms(cien), n_cien, cumple(cien, 30000)),
               "| RNF-A14 lanzar una corrida | ≤ 1 s | p95 %s ms (%d lanzamientos) | %s |" % (ms(lanza), n_lanza, cumple(lanza, 1000)),
               ""]
    texto = "\n".join(lineas)
    with open(os.path.join(carpeta, "resumen.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    return texto


if __name__ == "__main__":
    # La consola de Windows no siempre es UTF-8 (≥, «, ñ).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(analiza(sys.argv[1]))
