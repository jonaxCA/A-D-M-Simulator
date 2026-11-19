"""Comparacion de escenarios: costo de intervencion, impacto sanitario y frontera de Pareto.

Ambos ejes se MINIMIZAN: menos costo y menos impacto (fallecimientos,
hospitalizaciones, ...) son mejores. Un escenario esta dominado si otro cuesta
lo mismo o menos Y tiene el mismo impacto o menos, siendo estrictamente mejor
en al menos uno de los dos. Los no dominados forman la frontera: entre ellos no
hay una opcion objetivamente mejor, y elegir es una decision humana.

Costo de un escenario (modelo simple, declarado). D3: la frontera usa
personas-dia; los pesos van aparte, en la tabla, y nunca entran a la frontera.

    personas-dia (eje de la frontera):
        capas y testeo: poblacion x intensidad x dias_activos
            intensidad = reduccion | eficacia | deteccion  x cobertura x cumplimiento
        vacunacion:     dosis aplicadas en la corrida x personas-dia por dosis
    pesos (aparte):
        capas y testeo: costo_unitario [por habitante-dia] x las mismas personas-dia
        vacunacion:     costo_unitario [por dosis] x dosis aplicadas

Ni los costos unitarios ni el factor por dosis tienen valores por defecto: se
reciben por tipo de intervencion, con la misma trazabilidad que los parametros
de enfermedad: {"CIERRE_ESCUELAS": {"valor": 15.0, "fuente": "...", "supuesto": true}}.
Sin factor no hay frontera para un escenario con vacunacion; sin costo unitario,
sus pesos quedan sin dato y la comparacion sigue.
"""


from procesamiento.contrato import huella
from procesamiento.motor import INTERVENCIONES_CAPA, EscenarioInvalido, resolver
from procesamiento.trazabilidad import desempaca, es_numero, estado_traza

UNIDAD_COSTO = {
    **{tipo: "por_habitante_dia" for tipo in INTERVENCIONES_CAPA},
    "TESTEO_AISLAMIENTO": "por_habitante_dia",
    "VACUNACION": "por_dosis",
}
# Unidad del factor que lleva las dosis a personas-dia.
UNIDAD_FACTOR = "personas_dia_por_dosis"

METRICAS_IMPACTO = (
    "fallecimientos",
    "hospitalizaciones",
    "casos_acumulados",
    "pico_casos_activos",
    "pico_hospitalizados",
)


class ComparacionInvalida(ValueError):
    """La comparacion no se puede calcular. `errores` trae un mensaje por problema."""

    def __init__(self, errores):
        self.errores = list(errores)
        super().__init__("; ".join(self.errores))


def _dias_activos(iv, horizonte):
    # Mismo criterio que el motor: la intervencion actua en los dias 1..horizonte.
    inicio = max(iv["dia_inicio"], 1)
    fin = horizonte if iv["dia_fin"] is None else min(iv["dia_fin"], horizonte)
    return max(0, fin - inicio + 1)


def costo_escenario(escenario, resultado, costos, factores=None):
    """Personas-dia y pesos de un escenario, con su desglose por intervencion.

    `resultado` debe ser la salida de simular() para ESE escenario: la vacunacion
    se cuenta por las dosis que realmente se aplicaron en la corrida. `factores`
    trae las personas-dia por dosis de los tipos por dosis. Un tipo sin costo
    unitario deja los pesos en None y aparece en "faltan_pesos".
    """
    p = resolver(escenario)  # levanta EscenarioInvalido
    errores, desglose, traza, faltan = [], [], {}, []

    if not isinstance(resultado, dict) or resultado.get("huella_escenario") != huella(escenario):
        raise ComparacionInvalida(["El resultado no corresponde a este escenario (huella distinta)."])
    costos = costos if isinstance(costos, dict) else {}
    factores = factores if isinstance(factores, dict) else {}

    def valor(tabla, tipo, unidad, que):
        cifra, fuente, supuesto = desempaca(tabla[tipo])
        if not (es_numero(cifra) and cifra >= 0):
            errores.append(f"{que} de '{tipo}' debe ser un numero >= 0.")
            return None
        traza[(tipo, unidad)] = {"tipo": tipo, "valor": cifra, "unidad": unidad,
                                 "fuente": fuente, "estado": estado_traza(fuente, supuesto)}
        return float(cifra)

    def costo_unitario(tipo):
        if tipo not in costos:
            faltan.append(tipo)
            return None
        return valor(costos, tipo, UNIDAD_COSTO[tipo], "El costo unitario")

    def en_pesos(unitario, cantidad):
        return None if unitario is None else round(unitario * cantidad, 2)

    crudas = escenario.get("intervenciones") or []
    # resolver() ya garantizo que cada intervencion cruda es valida, asi que
    # ambas listas estan alineadas una a una.
    vacunaciones = []
    for cruda, iv in zip(crudas, p["intervenciones"]):
        tipo = iv["tipo"]
        if tipo == "VACUNACION":
            vacunaciones.append(iv)
            continue
        params = cruda.get("params") or {}
        if tipo == "TESTEO_AISLAMIENTO":
            fuerza = params["deteccion"]
        else:
            _, clave, defecto = INTERVENCIONES_CAPA[tipo]
            fuerza = params.get(clave, defecto)
        cobertura = 1.0 if cruda.get("cobertura") is None else cruda["cobertura"]
        cumplimiento = 1.0 if cruda.get("cumplimiento") is None else cruda["cumplimiento"]
        intensidad = fuerza * cobertura * cumplimiento
        dias = _dias_activos(iv, p["dias"])
        personas_dia = p["N"] * intensidad * dias
        desglose.append({
            "tipo": tipo, "dia_inicio": iv["dia_inicio"], "dia_fin": iv["dia_fin"],
            "dias_activos": dias, "intensidad": round(intensidad, 6),
            "cantidad": p["N"] * dias, "unidad": "habitante_dia",
            "costo": round(personas_dia, 2),
            "costo_pesos": en_pesos(costo_unitario(tipo), personas_dia),
        })

    if vacunaciones:
        # El resumen trae las dosis totales; con varias campanias de vacunacion
        # el factor y el costo por dosis son los mismos, asi que basta un renglon.
        dosis = resultado["resumen"]["dosis_aplicadas"]
        if "VACUNACION" in factores:
            factor = valor(factores, "VACUNACION", UNIDAD_FACTOR, "El factor de personas-dia por dosis")
        else:
            errores.append("Falta el factor de personas-dia por dosis de 'VACUNACION'.")
            factor = None
        if factor is not None:
            desglose.append({
                "tipo": "VACUNACION", "dia_inicio": min(v["dia_inicio"] for v in vacunaciones),
                "dia_fin": None, "dias_activos": None, "intensidad": None,
                "cantidad": dosis, "unidad": "dosis",
                "costo": round(factor * dosis, 2),
                "costo_pesos": en_pesos(costo_unitario("VACUNACION"), dosis),
            })

    if errores:
        raise ComparacionInvalida(errores)

    faltan = sorted(set(faltan))
    return {
        "personas_dia": round(sum(r["costo"] for r in desglose), 2),
        "pesos": None if faltan else round(sum(r["costo_pesos"] for r in desglose), 2),
        "desglose": desglose,
        "trazabilidad": list(traza.values()),
        "faltan_pesos": faltan,
    }


def frontera_pareto(puntos):
    """Marca los puntos dominados y regresa la frontera ordenada por costo.

    `puntos`: [{"id": ..., "costo": float, "impacto": float, ...}]. Regresa
    {"puntos": copia con "dominado" y "dominado_por", "frontera": [ids]}.
    Dos escenarios identicos en ambos ejes no se dominan entre si.
    """
    errores = []
    ids = [pt.get("id") for pt in puntos]
    if len(set(map(str, ids))) != len(ids):
        errores.append("Los ids de los escenarios deben ser unicos.")
    for pt in puntos:
        for eje in ("costo", "impacto"):
            if not (es_numero(pt.get(eje)) and pt[eje] >= 0):
                errores.append(f"Escenario '{pt.get('id')}': '{eje}' debe ser un numero >= 0.")
    if errores:
        raise ComparacionInvalida(errores)

    marcados = []
    for pt in puntos:
        dominado_por = [
            q["id"] for q in puntos
            if q is not pt
            and q["costo"] <= pt["costo"] and q["impacto"] <= pt["impacto"]
            and (q["costo"] < pt["costo"] or q["impacto"] < pt["impacto"])
        ]
        marcados.append({**pt, "dominado": bool(dominado_por), "dominado_por": dominado_por})

    frontera = sorted((m for m in marcados if not m["dominado"]),
                      key=lambda m: (m["costo"], m["impacto"], str(m["id"])))
    return {"puntos": marcados, "frontera": [m["id"] for m in frontera]}


def comparar(entradas, costos, metrica="fallecimientos", base=None, factores=None):
    """Compara corridas de varios escenarios en personas-dia, pesos e impacto sanitario.

    El eje de costo de la frontera es "costo", en personas-dia (D3); "costo_pesos"
    va aparte y es None si falta algun costo unitario.

    entradas: [{"id": "ESC-001", "nombre": "Sin intervencion",
                "escenario": {...}, "resultado": salida de simular()}]
    costos:   costo unitario en pesos por tipo de intervencion.
    factores: personas-dia por dosis de los tipos por dosis (VACUNACION).
    metrica:  eje de impacto, uno de METRICAS_IMPACTO.
    base:     id del escenario de referencia (normalmente "sin intervencion")
              para calcular impacto evitado y costo por unidad evitada.
    """
    errores, avisos = [], []
    if metrica not in METRICAS_IMPACTO:
        raise ComparacionInvalida([f"Metrica '{metrica}' no valida; usa una de: "
                                   + ", ".join(METRICAS_IMPACTO) + "."])
    if not isinstance(entradas, list) or len(entradas) < 2:
        raise ComparacionInvalida(["Se necesitan al menos dos escenarios para comparar."])

    filas, trazas, faltan = [], {}, set()
    for e in entradas:
        nombre = e.get("nombre") or e.get("id")
        try:
            costo = costo_escenario(e.get("escenario"), e.get("resultado"), costos, factores)
        except (EscenarioInvalido, ComparacionInvalida) as ex:
            errores.extend(f"{nombre}: {m}" for m in ex.errores)
            continue
        r = e["resultado"]
        filas.append({
            "id": e.get("id"), "nombre": nombre,
            "costo": costo["personas_dia"], "costo_pesos": costo["pesos"],
            "impacto": r["resumen"][metrica],
            "desglose_costo": costo["desglose"],
            "semilla": r["semilla"], "engine_version": r["engine_version"],
            "dias": r["dias"], "poblacion": r["poblacion"],
        })
        for t in costo["trazabilidad"]:
            trazas[(t["tipo"], t["unidad"])] = t
        faltan.update(costo["faltan_pesos"])

    if not errores:
        if len({f["dias"] for f in filas}) > 1:
            errores.append("Los escenarios tienen horizontes distintos; no son comparables.")
        if base is not None and base not in {f["id"] for f in filas}:
            errores.append(f"El escenario base '{base}' no esta entre los comparados.")
    if errores:
        raise ComparacionInvalida(errores)

    if len({f["poblacion"] for f in filas}) > 1:
        avisos.append("Los escenarios tienen poblaciones distintas; el impacto absoluto no es "
                      "directamente comparable.")
    if len({f["engine_version"] for f in filas}) > 1:
        avisos.append("Las corridas usan versiones distintas del motor.")
    sin_fuente = [t["tipo"] + (" (personas-dia por dosis)" if t["unidad"] == UNIDAD_FACTOR else "")
                  for t in trazas.values() if t["estado"] == "sin_fuente"]
    if sin_fuente:
        avisos.append("Costos sin fuente ni marca de supuesto: " + ", ".join(sin_fuente) + ".")
    if faltan:
        avisos.append("Falta el costo unitario en pesos de " + ", ".join(sorted(faltan))
                      + ": los pesos de los escenarios que lo usan quedan sin dato. "
                        "La frontera no los necesita.")

    pareto = frontera_pareto(filas)

    if base is not None:
        ref = next(f for f in pareto["puntos"] if f["id"] == base)
        for f in pareto["puntos"]:
            if f is ref:
                f.update(impacto_evitado=None, costo_adicional=None, costo_por_unidad_evitada=None)
                continue
            evitado = ref["impacto"] - f["impacto"]
            adicional = round(f["costo"] - ref["costo"], 2)
            f.update(impacto_evitado=evitado, costo_adicional=adicional,
                     costo_por_unidad_evitada=round(adicional / evitado, 2) if evitado > 0 else None)

    return {
        "metrica": metrica,
        "base": base,
        "filas": pareto["puntos"],
        "frontera": pareto["frontera"],
        "trazabilidad_costos": sorted(trazas.values(), key=lambda t: (t["tipo"], t["unidad"])),
        "modelo_costo": "personas-dia: poblacion x intensidad x dias (capas y testeo) y "
                        "dosis aplicadas x personas-dia por dosis (vacunacion). Pesos, aparte "
                        "y fuera de la frontera: unitario x esas personas-dia o x dosis aplicadas",
        "avisos": avisos,
    }
