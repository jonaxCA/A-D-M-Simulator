"""Analítica sobre los resultados de los motores: costo, impacto y frontera de Pareto.

No es parte de ningún motor. Recibe escenarios y salidas de simular() con la forma del
contrato (procesamiento/contrato.py), así que sirve igual para seir-ref, abm-ref y abm-gpu.
Del motor solo usa nombres públicos (`resolver`, `INTERVENCIONES_CAPA`, `EscenarioInvalido`),
y de la trazabilidad, procesamiento/trazabilidad.py.

    from procesamiento.analitica import comparar
    comparacion = comparar(entradas, costos, metrica="fallecimientos")
"""

from .pareto import (METRICAS_IMPACTO, UNIDAD_COSTO, ComparacionInvalida, comparar,
                     costo_escenario, frontera_pareto)

__all__ = [
    "METRICAS_IMPACTO",
    "UNIDAD_COSTO",
    "ComparacionInvalida",
    "comparar",
    "costo_escenario",
    "frontera_pareto",
]
