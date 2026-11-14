"""abm-ref: el modelo basado en agentes de EPIDEMIA, en Python y en CPU (D22, D23).

Cumple el mismo contrato que seir-ref (docs/contratos/motor/README.md): recibe el mismo
escenario, lo valida con el mismo `resolver` y regresa la misma forma de salida. Lo que cambia
es que cada persona es un agente con su hogar, su salón o su centro de trabajo, así que el
contagio se queda en esos grupos en vez de mezclarse con toda la población.

    from procesamiento.abm import simular
    resultado = simular(escenario, semilla=982314)
"""

from .modelo import ENGINE_VERSION, SIMPLIFICACIONES, simular

__all__ = ["ENGINE_VERSION", "SIMPLIFICACIONES", "simular"]
