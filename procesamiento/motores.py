"""Los motores implementados, por nombre (D2).

Es el único lugar que dice qué motores existen. Con él, el simulador corre cada corrida con el
motor de su lote, `corridas` sabe qué versión registrar al encolar, y `resultados` y la web
muestran las simplificaciones del motor que produjo un resultado. Un motor nuevo se agrega a
IMPLEMENTADOS, y las pruebas de conformidad (tests/test_contrato_motor.py) lo revisan solas.

Un motor puede estar implementado y no poderse correr en una máquina: abm-gpu necesita
pyflamegpu y una GPU de NVIDIA. `disponible()` lo dice, y del_nombre() no entrega un motor que
no se puede correr.
"""
from dataclasses import dataclass, field
from typing import Callable

from procesamiento import abm, abm_gpu
from procesamiento.contrato import MOTOR_REFERENCIA, MOTORES
from procesamiento.motor import ENGINE_VERSION as VERSION_SEIR
from procesamiento.motor import simular as simular_seir
from procesamiento.motor.modelo import SIMPLIFICACIONES as SIMPLIFICACIONES_SEIR

__all__ = ["IMPLEMENTADOS", "MOTOR_REFERENCIA", "Motor", "MotorNoDisponible", "de_version",
           "del_nombre"]


def _siempre():
    return True, None


@dataclass(frozen=True)
class Motor:
    nombre: str
    version: str
    simular: Callable
    simplificaciones: tuple
    # () -> (True, None) si se puede correr aquí; (False, motivo) si no.
    disponible: Callable = field(default=_siempre, compare=False)


IMPLEMENTADOS = {
    "seir-ref": Motor("seir-ref", VERSION_SEIR, simular_seir, tuple(SIMPLIFICACIONES_SEIR)),
    "abm-ref": Motor("abm-ref", abm.ENGINE_VERSION, abm.simular, tuple(abm.SIMPLIFICACIONES)),
    "abm-gpu": Motor("abm-gpu", abm_gpu.ENGINE_VERSION, abm_gpu.simular,
                     tuple(abm_gpu.SIMPLIFICACIONES), abm_gpu.disponible),
}

# Los resultados de antes de la migración 035 dicen python-ref-0.1: es seir-ref con otro nombre.
_NOMBRES_ANTERIORES = {"python-ref": "seir-ref"}


class MotorNoDisponible(ValueError):
    """El motor no existe, no está implementado, o no se puede correr en esta máquina (abm-gpu
    sin pyflamegpu o sin GPU)."""


def del_nombre(nombre):
    """El motor con ese nombre, listo para correr aquí; MotorNoDisponible si no."""
    if nombre in IMPLEMENTADOS:
        motor = IMPLEMENTADOS[nombre]
        listo, motivo = motor.disponible()
        if not listo:
            raise MotorNoDisponible("El motor %s no se puede correr en este simulador: %s"
                                    % (nombre, motivo))
        return motor
    if nombre in MOTORES:
        raise MotorNoDisponible("El motor %s todavía no está implementado en este simulador."
                                % nombre)
    raise MotorNoDisponible("Motor desconocido: %r." % (nombre,))


def de_version(engine_version):
    """El motor que produjo un resultado, por su engine_version (seir-ref-0.1 -> seir-ref);
    None si no se reconoce."""
    if not isinstance(engine_version, str) or "-" not in engine_version:
        return None
    nombre = engine_version.rsplit("-", 1)[0]
    return IMPLEMENTADOS.get(_NOMBRES_ANTERIORES.get(nombre, nombre))
