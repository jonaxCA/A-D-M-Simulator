"""Textos para mostrar, armados con lo que ya devolvio backend_web.

La capa de datos regresa datos crudos (numeros, fechas, claves) y la frase en
espanol que ve la persona se arma aqui. Asi una API que use backend_web recibe
datos y decide como mostrarlos.
"""


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
