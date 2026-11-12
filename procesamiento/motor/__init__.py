"""Motor epidemiologico de referencia de EPIDEMIA (seir-ref).

Modelo compartimental SEIR con hospitalizados, fallecidos y vacunados
protegidos, estratificado por grupo de edad, estocastico y reproducible:
la misma entrada con la misma semilla produce exactamente la misma salida
bajo la misma ENGINE_VERSION.

El paquete no depende de Flask ni de la base de datos. Recibe un diccionario
con el escenario y regresa un diccionario serializable a JSON; la capa web se
encarga de leer la version del escenario, guardar la corrida y sus estados.
Asi, cuando el motor pase a ser un worker o microservicio, se mueve tal cual.

La comparacion por costo e impacto (Pareto) no es parte del motor: vive en
procesamiento.analitica y solo usa los nombres publicos de aqui.

Uso minimo:

    from procesamiento.motor import simular
    resultado = simular(escenario, semilla=982314)
    resultado["resumen"]["fallecimientos"]
"""

from .modelo import AVISO_SIMULACION, ENGINE_VERSION, ErrorMotor, simular
from .parametros import (CAPAS_CONTACTO_SUPUESTO, INTERVENCIONES_CAPA, EscenarioInvalido,
                         resolver, validar_escenario)

__all__ = [
    "AVISO_SIMULACION",
    "ENGINE_VERSION",
    "CAPAS_CONTACTO_SUPUESTO",
    "INTERVENCIONES_CAPA",
    "ErrorMotor",
    "EscenarioInvalido",
    "resolver",
    "simular",
    "validar_escenario",
]
