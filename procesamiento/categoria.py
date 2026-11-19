"""Categoría de una corrida: exploratoria, predicción o resultado validado (D39).

El estado de cada versión de motor está en estado_validacion.json. Se cambia solo con su
evidencia en la ficha del simulador y en un PR revisado. Calibrar o validar es por enfermedad
y región: «calibrado» y «validado» son listas de {"enfermedad": código, "region": código}.
"""
import json
from pathlib import Path

ESTADO = json.loads((Path(__file__).with_name("estado_validacion.json")).read_text(encoding="utf-8"))

TEXTOS = {
    "exploratoria": "Simulación exploratoria: sirve para comparar escenarios entre sí, no para "
                    "anticipar cifras reales. El modelo no está calibrado ni validado con datos "
                    "observados de esta enfermedad y región.",
    "prediccion": "Predicción: el modelo está calibrado con datos observados de esta enfermedad "
                  "y región. Léase con su intervalo de incertidumbre.",
    "validada": "Resultado validado: el modelo reprodujo datos observados que no se usaron para "
                "calibrarlo, dentro de la tolerancia que declara su ficha.",
}


def categoria(engine_version, trazabilidad=(), enfermedad=None, region=None):
    """{"categoria", "modelo_verificado", "motivo", "texto"} de una corrida."""
    estado = ESTADO.get(engine_version) or {}
    verificado = bool(estado.get("verificado"))
    lugar = {"enfermedad": enfermedad, "region": region}
    supuestos = sorted({t["parametro"] for t in trazabilidad or ()
                        if t.get("estado") in ("supuesto", "sin_fuente")})
    if lugar not in estado.get("calibrado", []):
        motivo = "El modelo %s no está calibrado para esta enfermedad y región." % engine_version
        nombre = "exploratoria"
    elif supuestos:
        motivo = "Hay parámetros marcados como supuesto o sin fuente: %s." % ", ".join(supuestos)
        nombre = "exploratoria"
    elif lugar in estado.get("validado", []):
        motivo, nombre = "Calibrado y validado con datos independientes.", "validada"
    else:
        motivo, nombre = "Calibrado, todavía sin validar con datos independientes.", "prediccion"
    return {"categoria": nombre, "modelo_verificado": verificado, "motivo": motivo,
            "texto": TEXTOS[nombre]}
