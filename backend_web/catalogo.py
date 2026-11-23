"""Lectura y validacion de los formularios del catalogo de enfermedades, sin base.

Lo usan la web (que ya no toca la base, D36) y queries.py (que lo reexporta para los servicios).
"""
import math
import re
import unicodedata

from procesamiento.entrada_motor import PARAMETROS_SIMULACION, estado_parametros  # noqa: F401

RE_CODIGO_ENFERMEDAD = re.compile(r"^[A-Z][A-Z0-9_]{2,29}$")


def normaliza_codigo(valor):
    """'Dengue grave (2026)' -> 'DENGUE_GRAVE_2026'."""
    limpio = unicodedata.normalize("NFKD", (valor or "").strip())
    limpio = limpio.encode("ascii", "ignore").decode("ascii")
    limpio = re.sub(r"[^A-Za-z0-9]+", "_", limpio).strip("_").upper()
    return limpio[:30]


def valida_enfermedad(code, name):
    """code VARCHAR(30) unico, name VARCHAR(120) (004_catalogos.sql). Lista de errores."""
    errores = []
    if not code:
        errores.append("El código es obligatorio.")
    elif not RE_CODIGO_ENFERMEDAD.match(code):
        errores.append("El código debe empezar con letra y llevar entre 3 y 30 "
                       "caracteres (solo A-Z, 0-9 y guion bajo).")
    if not name:
        errores.append("El nombre es obligatorio.")
    elif len(name) > 120:
        errores.append("El nombre no puede pasar de 120 caracteres.")
    return errores


def parametros_desde_form(form, actuales=None):
    """(params, errores) con lo que venga del formulario.

    Conserva las claves que este formulario no edita (las informativas). Un valor sin fuente y
    sin marca de supuesto no se guarda.
    """
    params = dict(actuales or {})
    errores = []

    for spec in PARAMETROS_SIMULACION:
        clave = spec["clave"]
        crudo = (form.get(f"p_{clave}_valor") or "").strip()
        fuente = (form.get(f"p_{clave}_fuente") or "").strip()
        supuesto = form.get(f"p_{clave}_supuesto") == "on"

        if not crudo:
            params.pop(clave, None)
            continue

        try:
            valor = float(crudo.replace(",", "."))
        except ValueError:
            errores.append(f"{spec['etiqueta']}: «{crudo}» no es un número.")
            continue
        if not math.isfinite(valor) or not (spec["min"] <= valor <= spec["max"]):
            errores.append(f"{spec['etiqueta']}: debe estar entre {spec['min']:g} "
                           f"y {spec['max']:g} {spec['unidad']}.")
            continue
        if not fuente and not supuesto:
            errores.append(f"{spec['etiqueta']}: falta la fuente. Escríbela o marca "
                           "la casilla de supuesto.")
            continue

        params[clave] = {
            "valor": round(valor / 100, 10) if spec.get("porcentaje") else valor,
            "fuente": fuente or None,
            "supuesto": supuesto,
        }

    return params, errores
