"""Lectura de valores con trazabilidad, compartida por los motores y por la analítica.

Un parámetro de enfermedad o un costo llega como número directo o con su fuente (regla 8):
{"valor": 1.3, "fuente": "Biggerstaff et al., 2014", "supuesto": false}. Vivía dentro del
motor (motor/parametros.py); salió para que Pareto (procesamiento/analitica) no tenga que
importar nombres privados del motor.
"""
import math


def es_numero(x):
    """Un int o float finito. Un bool no cuenta, aunque Python lo trate como int."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def desempaca(crudo):
    """Separa valor, fuente y marca de supuesto.

    Acepta el numero directo, el formato con trazabilidad y el formato de
    distribucion de 010_datos_iniciales ({"dist": ..., "media": ...}), del que
    el motor de referencia, determinista en duraciones, solo usa la media.
    """
    if isinstance(crudo, dict) and "valor" in crudo:
        return crudo["valor"], crudo.get("fuente"), bool(crudo.get("supuesto", False))
    if isinstance(crudo, dict) and "media" in crudo:
        return crudo["media"], None, False
    return crudo, None, False


def estado_traza(fuente, supuesto):
    """El estado que va en la trazabilidad: supuesto, con_fuente o sin_fuente."""
    if supuesto:
        return "supuesto"
    return "con_fuente" if fuente else "sin_fuente"
