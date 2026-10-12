"""Textos para mostrar, armados con lo que ya devolvio backend_web.

La capa de datos regresa datos crudos (numeros, fechas, claves) y la frase en
espanol que ve la persona se arma aqui. Asi una API que use backend_web recibe
datos y decide como mostrarlos.
"""
from backend_web.simulaciones import id_simulacion

_MESES = ("Ene", "Feb", "Mar", "Abr", "May", "Jun",
          "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


def fecha_corta(valor):
    """'12 Oct 2026'. Se arma a mano en vez de con strftime porque %b depende
    del locale del sistema y aqui la vista siempre va en espanol."""
    if valor is None:
        return None
    return f"{valor.day:02d} {_MESES[valor.month - 1]} {valor.year}"


def fecha_hora(valor, segundos=False):
    """'2026-10-06 14:05', o con segundos para la bitacora."""
    if valor is None:
        return None
    return valor.strftime("%Y-%m-%d %H:%M:%S" if segundos else "%Y-%m-%d %H:%M")


_TENDENCIA = {"critico": "Critico", "alerta": "Alerta", "estable": "Estable"}

_ESTADOS_VERSION = {
    "borrador": "Borrador",
    "en_revision": "En revisión",
    "aprobado": "Aprobado",
    "rechazado": "Rechazado",
}


def tendencia_etiqueta(clave):
    """El semaforo de tendencia (queries._clasifica_tendencia). La clave es la
    etiqueta en minusculas, que es tambien la clase CSS del distintivo."""
    return _TENDENCIA[clave]


def estado_version(status):
    """El estado de una version de escenario tal como se lee; "—" si el
    escenario no tiene version vigente."""
    return _ESTADOS_VERSION.get(status, "—")


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


_ESTADOS_USUARIO = {"activo": "Activo", "pendiente": "Pendiente", "inactivo": "Inactivo"}


def estado_usuario(clave):
    """El estado de una cuenta (queries.get_usuarios_lista). La clave es
    tambien la clase CSS del distintivo."""
    return _ESTADOS_USUARIO[clave]


# ---------------------------------------------------------------------------
# Bitacora (queries.get_auditoria_lista y get_acciones_auditoria)
# ---------------------------------------------------------------------------
# El estado de cada evento usa las clases de distintivo que ya existen en
# styles.css (correcto/pendiente/fallido/inactivo).

_ACCIONES_FALLIDAS = ("LOGIN_FAILED", "PERMISSION_DENIED")

_DESCRIPCION_POR_ACCION = {
    "LOGIN": "Inicio de sesion exitoso",
    "LOGIN_FAILED": "Intento de inicio de sesion fallido",
    "LOGOUT": "Cierre de sesion",
    "EXPORT": "Exportacion de datos",
    "CREATE": "Alta de registro",
    "UPDATE": "Modificacion de registro",
    "DELETE": "Baja de registro",
    "PUBLISH": "Publicacion",
    "RUN": "Ejecucion de simulacion",
    "CANCEL": "Cancelacion",
    "SYNC": "Sincronizacion",
    "PERMISSION_DENIED": "Acceso denegado por permisos",
}

# Texto y estado de cada etapa de una corrida (data_after['estado'] de un
# evento RUN), en el orden en que ocurren. Todas las etapas comparten
# action='RUN': si la bitacora solo mirara la accion, se verian identicas,
# incluida la fallida como "Correcto".
_RUN_ETAPA = {
    "encolado": ("Simulacion solicitada", "Pendiente"),
    "ejecutando": ("Simulacion en ejecucion (inicio)", "Pendiente"),
    "completado": ("Simulacion completada", "Correcto"),
    "fallido": ("Simulacion fallida", "Fallido"),
    "cancelado": ("Simulacion cancelada", "Inactivo"),
    "abortado_antes_de_ejecutar": (
        "Simulacion no iniciada (ya tomada por otro proceso)", "Inactivo",
    ),
}

# Envio, aprobacion y rechazo de una version quedan como UPDATE en audit_log;
# lo que los distingue es data_after['status'].
_VERSION_ETAPA = {
    "en_revision": "Version enviada a revision",
    "aprobado": "Version aprobada",
    "rechazado": "Version rechazada",
}


def _resumen_indicadores_run(data_after):
    """Resumen corto de resultado.resumen para la descripcion de una etapa
    'completado': la corrida completada se ve con sus indicadores."""
    indicadores = (data_after or {}).get("indicadores") or {}
    partes = []
    if "tasa_ataque" in indicadores:
        try:
            partes.append(f"tasa de ataque {float(indicadores['tasa_ataque']) * 100:.1f}%")
        except (TypeError, ValueError):
            pass
    if "casos_acumulados" in indicadores:
        partes.append(f"{indicadores['casos_acumulados']} casos acumulados")
    if "fallecimientos" in indicadores:
        partes.append(f"{indicadores['fallecimientos']} fallecimientos")
    return ", ".join(partes)


def describe_evento_auditoria(action, entity_id, data_after, entity_type=None):
    """(descripcion, estado) de un evento de audit_log. RUN y el cambio de
    estado de una version leen data_after; las demas acciones siguen la regla
    general: LOGIN_FAILED/PERMISSION_DENIED = Fallido, todo lo demas =
    Correcto."""
    if action == "RUN":
        etapa = (data_after or {}).get("estado")
        base, estado = _RUN_ETAPA.get(etapa, (_DESCRIPCION_POR_ACCION["RUN"], "Correcto"))
        try:
            identificador = f" {id_simulacion(entity_id)}" if entity_id else ""
        except (ValueError, TypeError):
            identificador = ""
        if etapa == "completado":
            resumen = _resumen_indicadores_run(data_after)
            descripcion = f"{base}{identificador}" + (f": {resumen}" if resumen else "")
        elif etapa == "fallido":
            error = (data_after or {}).get("error") or "sin detalle"
            descripcion = f"{base}{identificador}: {error}"
        else:
            descripcion = f"{base}{identificador}"
        return descripcion, estado
    if action == "UPDATE" and entity_type == "scenario_versions":
        etapa = (data_after or {}).get("status")
        if etapa in _VERSION_ETAPA:
            numero = (data_after or {}).get("version_number")
            sufijo = f" (v{numero})" if numero else ""
            return f"{_VERSION_ETAPA[etapa]}{sufijo}", "Correcto"

    descripcion = _DESCRIPCION_POR_ACCION.get(action, action)
    estado = "Fallido" if action in _ACCIONES_FALLIDAS else "Correcto"
    return descripcion, estado


def filas_bitacora(eventos):
    """Los eventos de queries.get_auditoria_lista con su descripcion y su
    estado."""
    filas = []
    for e in eventos:
        descripcion, estado = describe_evento_auditoria(e["accion"], e["entidad_id"],
                                                        e["datos"], e["modulo"])
        filas.append({**e, "descripcion": descripcion, "estado": estado})
    return filas


def opciones_accion(valores):
    """Las opciones del filtro Accion a partir de queries.get_acciones_auditoria:
    cada accion con su texto y despues las etapas de RUN en el orden en que
    ocurren; una etapa desconocida va al final."""
    acciones = [v for v in valores if not v.startswith("RUN::")]
    etapas = [v.split("::", 1)[1] for v in valores if v.startswith("RUN::")]
    orden = list(_RUN_ETAPA)
    etapas.sort(key=lambda e: orden.index(e) if e in orden else len(orden))
    opciones = [{"valor": a, "etiqueta": _DESCRIPCION_POR_ACCION.get(a, a)} for a in acciones]
    for etapa in etapas:
        etiqueta, _estado = _RUN_ETAPA.get(etapa, (f"Ejecucion de simulacion ({etapa})", "Correcto"))
        opciones.append({"valor": f"RUN::{etapa}", "etiqueta": etiqueta})
    return opciones


def monitoreo_insights(zonas, edades, totales, dias):
    """Los 3 textos de las tarjetas de arriba de Monitoreo. Son funcion pura de
    lo que ya se consulto: no vuelve a pegarle a la base.

    `zonas` son todas las del ambito, en un orden fijo: con un empate en la
    variacion gana la primera, asi que una pagina de la tabla o el orden que
    eligio la persona cambiarian el texto. Solo se nombra una zona si alguna
    aumento; si la mayor variacion es 0 o negativa, nombrar una seria mentir."""
    con_casos = [z for z in zonas if z["casos"]]
    if not con_casos:
        geografica = "Todavía no hay casos capturados en el periodo seleccionado."
    else:
        top = max(con_casos, key=lambda z: z["variacion"])
        if top["variacion"] > 0:
            geografica = (f"El mayor cambio (+{top['variacion']}%) se registra en "
                          f"{top['zona']} durante los últimos 7 días.")
        else:
            geografica = "Ninguna zona aumentó sus casos en los últimos 7 días."

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
