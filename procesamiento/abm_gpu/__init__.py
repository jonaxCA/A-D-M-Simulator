"""abm-gpu: el modelo basado en agentes de abm-ref, en FLAME GPU 2 (D23).

Cumple el mismo contrato que seir-ref y abm-ref (docs/contratos/motor/README.md). Necesita
pyflamegpu y una GPU de NVIDIA; sin ellos, importar este paquete funciona, pero simular()
levanta SinFlameGPU. disponible() dice si se puede usar en esta máquina.

    from procesamiento.abm_gpu import simular
    resultado = simular(escenario, semilla=982314)
"""

from .entorno import SinFlameGPU, disponible
from .modelo import ENGINE_VERSION, SIMPLIFICACIONES, simular

__all__ = ["ENGINE_VERSION", "SIMPLIFICACIONES", "SinFlameGPU", "disponible", "simular"]
