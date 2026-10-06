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


_ACTIVIDAD = {"con_casos": "Con casos activos", "historico": "Solo histórico",
              "sin_casos": "Sin casos"}


def actividad_etiqueta(clave):
    """La situacion epidemiologica de una enfermedad (queries._actividad)."""
    return _ACTIVIDAD[clave]


def estado_catalogo(activa):
    return "Activa" if activa else "Inactiva"


def valor_parametro(parametro):
    """Valor de un parametro de simulacion con su unidad, para leer: una
    entrada de queries.estado_parametros()["detalle"]. Las tasas se guardan
    0-1 y se muestran en %."""
    valor = parametro["valor"]
    if valor is None:
        return None
    mostrado = valor * 100 if parametro.get("porcentaje") else valor
    return f"{mostrado:g} {parametro['unidad']}".strip()


def _inicio_de_grupo(par):
    """Ordena "0-19", "20-39", ..., "80+" por la edad con que empiezan. Lo que
    no empiece con un numero se va al final, en orden alfabetico."""
    clave = str(par[0])
    digitos = ""
    for c in clave:
        if not c.isdigit():
            break
        digitos += c
    return (0, int(digitos), clave) if digitos else (1, 0, clave)


def _numero_corto(valor):
    """3.11e-05 se lee mejor como 0.00311%."""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f"{valor * 100:.4g}%"
    return str(valor)


def texto_informativo(valor):
    """Un parametro informativo en una linea. Una tabla por grupo de edad va
    ordenada por edad, no por el orden en que JSONB devuelve las claves: sin
    esto "80+" sale primero y la tabla se lee al reves de como se piensa."""
    if isinstance(valor, dict):
        return ", ".join(f"{k}: {_numero_corto(v)}"
                         for k, v in sorted(valor.items(), key=_inicio_de_grupo))
    return str(valor)


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
