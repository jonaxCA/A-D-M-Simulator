"""Textos para mostrar, armados con lo que ya devolvio backend_web.

La capa de datos regresa datos crudos (numeros, fechas, claves) y la frase en
espanol que ve la persona se arma aqui. Asi una API que use backend_web recibe
datos y decide como mostrarlos.
"""

_MESES = ("Ene", "Feb", "Mar", "Abr", "May", "Jun",
          "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


def fecha_corta(valor):
    """'12 Oct 2026'. Se arma a mano en vez de con strftime porque %b depende
    del locale del sistema y aqui la vista siempre va en espanol."""
    if valor is None:
        return None
    return f"{valor.day:02d} {_MESES[valor.month - 1]} {valor.year}"


def fuente_etiqueta(fuente):
    """El texto del distintivo de una fuente de poblacion
    (queries.get_regiones_catalogo y get_estado_nl). Una cifra que un
    administrador corrigio nunca se le atribuye a INEGI."""
    if fuente["tipo"] == "manual":
        return "Corrección manual"
    if fuente["tipo"] == "agregado":
        return "Suma de los 51 municipios"
    return fuente["fuente"]


def fuente_detalle(fuente):
    """El texto al pasar el cursor sobre el distintivo, o None."""
    if fuente["tipo"] == "manual":
        return (f"Corregido por {fuente['por'] or 'un administrador'} el "
                f"{fecha_corta(fuente['fecha'])}: {fuente['motivo']}")
    if fuente["tipo"] == "derivado":
        return "Se calcula a partir de las bandas de edad; no se captura aparte."
    return None


def monitoreo_insights(zonas, edades, totales, dias):
    """Los 3 textos de las tarjetas de arriba de Monitoreo. Son funcion pura de
    lo que ya se consulto: no vuelve a pegarle a la base."""
    con_casos = [z for z in zonas if z["casos"]]
    if con_casos:
        top = max(con_casos, key=lambda z: z["variacion"])
        signo = "+" if top["variacion"] >= 0 else ""
        geografica = (f"El mayor cambio ({signo}{top['variacion']}%) se registra en "
                      f"{top['zona']} durante los últimos 7 días.")
    else:
        geografica = "Todavía no hay casos capturados en el periodo seleccionado."

    pct = totales["casos_pct"]
    verbo = "aumentó" if pct > 0 else ("disminuyó" if pct < 0 else "se mantuvo")
    global_txt = (f"La incidencia general {verbo} un {abs(pct)}% respecto al periodo "
                  f"anterior de {dias} días.")

    activos = [e for e in edades if e["casos"]]
    if activos:
        peor = max(activos, key=lambda e: e["casos"])
        critica = (f"El grupo con más casos es el de {peor['grupo']} años "
                   f"({peor['casos']:,} casos).")
    else:
        critica = "Sin casos con edad registrada en el periodo."

    return {"geografica": geografica, "global": global_txt, "critica": critica}
