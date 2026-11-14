"""Los motores implementados, por nombre (D2).

Es el único lugar que dice qué motores existen. Con él, el simulador corre cada corrida con el
motor de su lote, `corridas` sabe qué versión registrar al encolar, y `resultados` y la web
muestran las simplificaciones del motor que produjo un resultado. Un motor nuevo se agrega a
IMPLEMENTADOS, y las pruebas de conformidad (tests/test_contrato_motor.py) lo revisan solas.
"""
from dataclasses import dataclass
from typing import Callable

from procesamiento import abm
from procesamiento.contrato import MOTOR_REFERENCIA, MOTORES
from procesamiento.motor import ENGINE_VERSION as VERSION_SEIR
from procesamiento.motor import simular as simular_seir
from procesamiento.motor.modelo import SIMPLIFICACIONES as SIMPLIFICACIONES_SEIR

__all__ = ["IMPLEMENTADOS", "MOTOR_REFERENCIA", "Motor", "MotorNoDisponible", "de_version",
           "del_nombre"]


@dataclass(frozen=True)
class Motor:
    nombre: str
    version: str
    simular: Callable
    simplificaciones: tuple


IMPLEMENTADOS = {
    "seir-ref": Motor("seir-ref", VERSION_SEIR, simular_seir, tuple(SIMPLIFICACIONES_SEIR)),
    "abm-ref": Motor("abm-ref", abm.ENGINE_VERSION, abm.simular, tuple(abm.SIMPLIFICACIONES)),
}

# Los resultados de antes de la migración 035 dicen python-ref-0.1: es seir-ref con otro nombre.
_NOMBRES_ANTERIORES = {"python-ref": "seir-ref"}


class MotorNoDisponible(ValueError):
    """El motor no existe, o existe en D2 pero todavía no está implementado (abm-gpu)."""


def del_nombre(nombre):
    """El motor implementado con ese nombre; MotorNoDisponible si no lo hay."""
    if nombre in IMPLEMENTADOS:
        return IMPLEMENTADOS[nombre]
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
