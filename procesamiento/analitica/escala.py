"""Factor de escala de un escenario (D6, opción C).

`population_size` de una versión cuenta agentes simulados, no habitantes. El motor nunca ve el
factor: simula esos agentes y sus resultados son de esos agentes. Fuera del motor se calcula
cuántos habitantes representa cada uno,

    factor = habitantes de la región (regions.population, Censo 2020) / agentes simulados,

y con él, cuántos habitantes representan los conteos del resumen. Una versión estratificada
toma la población completa del censo, así que su factor es 1; solo una sin estratificar puede
simular menos agentes que habitantes.

Los números escalados son una extrapolación: suponen que los habitantes que no se simularon se
comportan como los que sí. Se presentan como aproximados y junto a los de la corrida, nunca en
su lugar.
"""
from procesamiento.trazabilidad import es_numero

FUENTE_HABITANTES = "regions.population (Censo 2020 de INEGI)"

# Conteos del resumen que se escalan. tasa_ataque y los días de pico no: no cuentan personas.
INDICADORES_ESCALABLES = (
    "casos_acumulados", "casos_activos_final", "pico_casos_activos", "pico_nuevos_casos",
    "hospitalizaciones", "pico_hospitalizados", "fallecimientos", "vacunados_protegidos",
    "dosis_aplicadas",
)


def factor_de_escala(habitantes, agentes):
    """{"agentes", "habitantes", "factor", "fuente", "avisos"}; factor None si no se puede
    calcular (sin habitantes o sin agentes)."""
    avisos = []
    if not (es_numero(habitantes) and habitantes > 0 and es_numero(agentes) and agentes > 0):
        return {"agentes": agentes, "habitantes": habitantes, "factor": None,
                "fuente": FUENTE_HABITANTES,
                "avisos": ["No se puede calcular el factor de escala: falta la población de la "
                           "región o el número de agentes."]}
    factor = habitantes / agentes
    if factor < 1:
        avisos.append("Hay más agentes simulados (%s) que habitantes en la región (%s): cada "
                      "agente representa menos de una persona." % (f"{agentes:,}", f"{habitantes:,}"))
    return {"agentes": int(agentes), "habitantes": int(habitantes), "factor": round(factor, 4),
            "fuente": FUENTE_HABITANTES, "avisos": avisos}


def representados(resumen, escala):
    """Los conteos del resumen llevados a habitantes, redondeados; {} si no hay factor."""
    if escala.get("factor") is None or not isinstance(resumen, dict):
        return {}
    # Con el cociente exacto, no con el factor redondeado que se muestra.
    factor = escala["habitantes"] / escala["agentes"]
    return {campo: round(resumen[campo] * factor) for campo in INDICADORES_ESCALABLES
            if es_numero(resumen.get(campo))}
