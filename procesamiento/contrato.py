"""Contrato de los motores de simulación (D2): lo que entra y lo que sale.

Los tres motores, seir-ref (procesamiento/motor), abm-ref y abm-gpu, se llaman igual:

    simular(escenario: dict, semilla: int) -> dict

y regresan un diccionario con la misma forma. Aquí está esa forma en código, para que las
pruebas de cada motor la revisen con `revisa_salida`. El texto para personas está en
docs/contratos/motor/README.md, y sus ejemplos se regeneran con:

    python -m procesamiento.contrato --ejemplos

No depende de ningún motor: un motor nuevo importa de aquí, no al revés.
"""
import hashlib
import json
import math
import re
import sys
from pathlib import Path

# Nombres de los motores (D2, migración 035). El de referencia es el que siempre existe.
MOTORES = ("seir-ref", "abm-ref", "abm-gpu")
MOTOR_REFERENCIA = "seir-ref"

# La salida de simular(). Un motor puede agregar llaves propias (seir-ref agrega
# numpy_version), pero estas son obligatorias y significan lo mismo en los tres.
LLAVES_SALIDA = (
    "engine_version", "semilla", "huella_escenario", "dias", "poblacion", "serie",
    "resumen", "trazabilidad_parametros", "simplificaciones", "avisos",
)
COMPARTIMENTOS = ("S", "E", "I", "R", "H", "D", "V")
CAMPOS_SERIE = ("dia",) + COMPARTIMENTOS + (
    "casos_activos", "nuevos_casos", "nuevas_hospitalizaciones", "nuevas_defunciones",
    "dosis_aplicadas",
)
# Las columnas generadas de simulation_results (014) leen casos_acumulados,
# hospitalizaciones, fallecimientos, pico_casos_activos, dia_pico y tasa_ataque: si faltan,
# la base no da error, deja columnas vacías.
CAMPOS_RESUMEN = (
    "casos_acumulados", "casos_activos_final", "pico_casos_activos", "dia_pico",
    "pico_nuevos_casos", "dia_pico_nuevos_casos", "hospitalizaciones", "pico_hospitalizados",
    "dia_pico_hospitalizados", "fallecimientos", "tasa_ataque", "vacunados_protegidos",
    "dosis_aplicadas", "desglose_por_grupo",
)
CAMPOS_GRUPO = ("grupo", "poblacion", "casos", "fallecimientos", "vacunados_protegidos",
                "dosis_aplicadas")
CAMPOS_TRAZA = ("parametro", "valor", "fuente", "estado")
ESTADOS_TRAZA = ("con_fuente", "sin_fuente", "supuesto")

# El escenario de los ejemplos del contrato y de las pruebas de conformidad. La estructura
# por edad es la de Nuevo León (Censo 2020) llevada a 50 000 personas; los parámetros de la
# enfermedad son supuestos ilustrativos, marcados como tales (regla 8).
_SUPUESTO = "Ejemplo del contrato del motor, no validado"
ESCENARIO_EJEMPLO = {
    "poblacion": {"0-19": 16070, "20-39": 16192, "40-59": 12067, "60-79": 4897, "80+": 774},
    "infectados_iniciales": 20,
    "dias": 30,
    "enfermedad": {
        "r0": {"valor": 1.6, "supuesto": True, "fuente": _SUPUESTO},
        "incubacion_dias": {"valor": 2.0, "supuesto": True, "fuente": _SUPUESTO},
        "infeccioso_dias": {"valor": 5.0, "supuesto": True, "fuente": _SUPUESTO},
        "dias_hospitalizacion": {"valor": 5.0, "supuesto": True, "fuente": _SUPUESTO},
        "tasa_hospitalizacion": {"valor": {"0-19": 0.002, "20-39": 0.003, "40-59": 0.008,
                                           "60-79": 0.03, "80+": 0.08},
                                 "supuesto": True, "fuente": _SUPUESTO},
        "letalidad": {"valor": {"0-19": 0.00001, "20-39": 0.00005, "40-59": 0.0003,
                                "60-79": 0.002, "80+": 0.008},
                      "supuesto": True, "fuente": _SUPUESTO},
    },
    "intervenciones": [
        {"tipo": "CIERRE_ESCUELAS", "dia_inicio": 7, "dia_fin": 21, "cobertura": 1.0,
         "cumplimiento": 0.9, "params": {"reduccion": 1.0}},
        {"tipo": "VACUNACION", "dia_inicio": 5, "cobertura": 0.5,
         "params": {"eficacia": 0.9, "dosis_diarias": 300, "prioridad": "edad_desc"}},
    ],
}
SEMILLA_EJEMPLO = 20261112

CARPETA_EJEMPLOS = Path(__file__).resolve().parents[1] / "docs" / "contratos" / "motor" / "ejemplos"


def huella(escenario):
    """SHA-256 de la entrada canónica. Todos los motores la calculan igual, así que dos
    corridas de motores distintos con la misma huella simularon el mismo escenario."""
    canonico = json.dumps(escenario, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), default=str)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _entero(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _entero_no_negativo(x):
    return _entero(x) and x >= 0


def revisa_salida(salida, escenario, semilla, motor):
    """Lista de problemas de `salida` frente al contrato; vacía si lo cumple.

    `escenario` y `semilla` son los que recibió simular(), y `motor` es su nombre
    (seir-ref, abm-ref o abm-gpu)."""
    if not isinstance(salida, dict):
        return ["la salida no es un diccionario"]
    problemas = ["falta la llave %r" % k for k in LLAVES_SALIDA if k not in salida]
    if problemas:
        return problemas
    try:
        json.dumps(salida, allow_nan=False)
    except (TypeError, ValueError) as exc:
        problemas.append("la salida no es JSON estricto: %s" % exc)

    if motor not in MOTORES:
        problemas.append("motor desconocido: %r" % motor)
    if not (isinstance(salida["engine_version"], str)
            and re.fullmatch(re.escape(motor) + r"-\d+\.\d+(\.\d+)?", salida["engine_version"])):
        problemas.append("engine_version debe ser '%s-<versión>': %r"
                         % (motor, salida["engine_version"]))
    if salida["semilla"] != semilla:
        problemas.append("semilla: se pidió %r y regresó %r" % (semilla, salida["semilla"]))
    if salida["huella_escenario"] != huella(escenario):
        problemas.append("huella_escenario no es la SHA-256 de la entrada canónica")
    if salida["dias"] != escenario.get("dias"):
        problemas.append("dias: el escenario pide %r y regresó %r"
                         % (escenario.get("dias"), salida["dias"]))

    poblacion = salida["poblacion"]
    if not (_entero(poblacion) and poblacion > 0):
        problemas.append("poblacion debe ser un entero positivo: %r" % (poblacion,))
        return problemas

    problemas += _revisa_serie(salida["serie"], salida["dias"], poblacion)
    if not problemas:
        problemas += _revisa_resumen(salida["resumen"], salida["serie"], poblacion,
                                     escenario.get("infectados_iniciales"))
    problemas += _revisa_textos(salida)
    return problemas


def _revisa_serie(serie, dias, poblacion):
    if not isinstance(serie, list) or not _entero(dias) or len(serie) != dias + 1:
        return ["serie debe tener dias + 1 filas (del día 0 al último)"]
    problemas = []
    for esperado, fila in enumerate(serie):
        if not isinstance(fila, dict) or set(fila) != set(CAMPOS_SERIE):
            problemas.append("día %d: los campos deben ser %s" % (esperado, ", ".join(CAMPOS_SERIE)))
            continue
        if fila["dia"] != esperado:
            problemas.append("la fila %d dice dia=%r" % (esperado, fila["dia"]))
        malos = [c for c in CAMPOS_SERIE if not _entero_no_negativo(fila[c])]
        if malos:
            problemas.append("día %d: %s deben ser enteros >= 0" % (esperado, ", ".join(malos)))
            continue
        if sum(fila[c] for c in COMPARTIMENTOS) != poblacion:
            problemas.append("día %d: S+E+I+R+H+D+V no suma la población" % esperado)
        if fila["casos_activos"] != fila["E"] + fila["I"] + fila["H"]:
            problemas.append("día %d: casos_activos debe ser E + I + H" % esperado)
    return problemas[:10]


def _revisa_resumen(resumen, serie, poblacion, infectados_iniciales):
    if not isinstance(resumen, dict) or set(resumen) != set(CAMPOS_RESUMEN):
        return ["resumen: los campos deben ser %s" % ", ".join(CAMPOS_RESUMEN)]
    problemas = []
    ultima = serie[-1]
    if _entero(infectados_iniciales):
        acumulados = infectados_iniciales + sum(f["nuevos_casos"] for f in serie)
        if resumen["casos_acumulados"] != acumulados:
            problemas.append("casos_acumulados debe ser infectados_iniciales + la suma de "
                             "nuevos_casos")
    esperado = {
        "casos_activos_final": ultima["casos_activos"],
        "fallecimientos": ultima["D"],
        "vacunados_protegidos": ultima["V"],
        "hospitalizaciones": sum(f["nuevas_hospitalizaciones"] for f in serie),
        "dosis_aplicadas": sum(f["dosis_aplicadas"] for f in serie),
        "pico_casos_activos": max(f["casos_activos"] for f in serie),
        "pico_nuevos_casos": max(f["nuevos_casos"] for f in serie),
        "pico_hospitalizados": max(f["H"] for f in serie),
    }
    for campo, valor in esperado.items():
        if resumen[campo] != valor:
            problemas.append("%s no coincide con la serie" % campo)
    for campo_dia, campo_pico, campo_serie in (
            ("dia_pico", "pico_casos_activos", "casos_activos"),
            ("dia_pico_nuevos_casos", "pico_nuevos_casos", "nuevos_casos"),
            ("dia_pico_hospitalizados", "pico_hospitalizados", "H")):
        dia = resumen[campo_dia]
        if not (_entero(dia) and 0 <= dia < len(serie)
                and serie[dia][campo_serie] == resumen[campo_pico]):
            problemas.append("%s debe ser el día en que la serie alcanza %s"
                             % (campo_dia, campo_pico))
    tasa = resumen["tasa_ataque"]
    if not (isinstance(tasa, (int, float)) and not isinstance(tasa, bool) and math.isfinite(tasa)
            and 0 <= tasa <= 1):
        problemas.append("tasa_ataque debe estar entre 0 y 1")

    grupos = resumen["desglose_por_grupo"]
    if not isinstance(grupos, list) or not grupos:
        return problemas + ["desglose_por_grupo debe ser una lista con al menos un grupo"]
    if any(not isinstance(g, dict) or set(g) != set(CAMPOS_GRUPO) for g in grupos):
        return problemas + ["desglose_por_grupo: los campos deben ser %s" % ", ".join(CAMPOS_GRUPO)]
    for campo, total in (("poblacion", poblacion), ("casos", resumen["casos_acumulados"]),
                         ("fallecimientos", resumen["fallecimientos"]),
                         ("vacunados_protegidos", resumen["vacunados_protegidos"]),
                         ("dosis_aplicadas", resumen["dosis_aplicadas"])):
        if sum(g[campo] for g in grupos) != total:
            problemas.append("desglose_por_grupo: la suma de %s no da el total" % campo)
    return problemas


def _revisa_textos(salida):
    problemas = []
    trazas = salida["trazabilidad_parametros"]
    if not isinstance(trazas, list) or any(
            not isinstance(t, dict) or set(t) != set(CAMPOS_TRAZA)
            or t["estado"] not in ESTADOS_TRAZA for t in trazas):
        problemas.append("trazabilidad_parametros: cada elemento lleva %s, y estado es uno de %s"
                         % (", ".join(CAMPOS_TRAZA), ", ".join(ESTADOS_TRAZA)))
    for llave in ("simplificaciones", "avisos"):
        valor = salida[llave]
        if not isinstance(valor, list) or any(not isinstance(t, str) or not t.strip()
                                              for t in valor):
            problemas.append("%s debe ser una lista de textos" % llave)
    if not salida["simplificaciones"]:
        problemas.append("simplificaciones no puede ir vacía: todo motor simplifica algo")
    return problemas


def escribe_ejemplos(simular, carpeta=CARPETA_EJEMPLOS):
    """Escribe entrada.json y salida.json con la salida del motor de referencia."""
    carpeta.mkdir(parents=True, exist_ok=True)
    salida = simular(ESCENARIO_EJEMPLO, SEMILLA_EJEMPLO)
    for nombre, datos in (("entrada.json", {"escenario": ESCENARIO_EJEMPLO,
                                            "semilla": SEMILLA_EJEMPLO}),
                          ("salida.json", salida)):
        (carpeta / nombre).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
    return carpeta


if __name__ == "__main__":
    if sys.argv[1:] != ["--ejemplos"]:
        sys.exit("Uso: python -m procesamiento.contrato --ejemplos")
    from procesamiento.motor import simular as simular_referencia

    print("Escritos en", escribe_ejemplos(simular_referencia))
