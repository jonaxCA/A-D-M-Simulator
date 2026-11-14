"""Analítica sobre los resultados de los motores: costo, impacto, frontera de Pareto y el
factor de escala de D6.

No es parte de ningún motor. Recibe escenarios y salidas de simular() con la forma del
contrato (procesamiento/contrato.py), así que sirve igual para seir-ref, abm-ref y abm-gpu.
Del motor solo usa nombres públicos (`resolver`, `INTERVENCIONES_CAPA`, `EscenarioInvalido`),
y de la trazabilidad, procesamiento/trazabilidad.py.

    from procesamiento.analitica import comparar
    comparacion = comparar(entradas, costos, metrica="fallecimientos")
"""

from .escala import INDICADORES_ESCALABLES, factor_de_escala, representados
from .pareto import (METRICAS_IMPACTO, UNIDAD_COSTO, ComparacionInvalida, comparar,
                     costo_escenario, frontera_pareto)

__all__ = [
    "INDICADORES_ESCALABLES",
    "METRICAS_IMPACTO",
    "UNIDAD_COSTO",
    "ComparacionInvalida",
    "comparar",
    "costo_escenario",
    "factor_de_escala",
    "frontera_pareto",
    "representados",
]
