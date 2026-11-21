"""Chequeo rápido de abm-gpu en esta máquina o en el contenedor simulador-gpu.

    python -m procesamiento.abm_gpu

Corre dos veces el escenario de ejemplo del contrato (la primera compila), revisa la salida
contra el contrato y que la telemetría de FLAME GPU esté apagada. Sale con 1 si algo falla.
"""
import copy
import sys
import time

from procesamiento import contrato

from . import ENGINE_VERSION, disponible, entorno, simular


def main():
    listo, motivo = disponible()
    if not listo:
        print("abm-gpu no corre aquí:", motivo)
        return 1
    fg = entorno.carga()
    print("%s con pyflamegpu %s; telemetría %s" % (
        ENGINE_VERSION, fg.__version__, "ENCENDIDA" if fg.Telemetry.isEnabled() else "apagada"))
    esc = contrato.ESCENARIO_EJEMPLO
    for vuelta in ("con compilación", "ya compilado"):
        inicio = time.perf_counter()
        salida = simular(copy.deepcopy(esc), contrato.SEMILLA_EJEMPLO)
        print("%s agentes, %s días, %s: %.2f s" % (
            salida["poblacion"], salida["dias"], vuelta, time.perf_counter() - inicio))
    problemas = contrato.revisa_salida(salida, esc, contrato.SEMILLA_EJEMPLO, "abm-gpu")
    print("contrato:", "cumple" if not problemas else problemas)
    print("tasa de ataque: %.4f" % salida["resumen"]["tasa_ataque"])
    return 1 if problemas or fg.Telemetry.isEnabled() else 0


if __name__ == "__main__":
    sys.exit(main())
