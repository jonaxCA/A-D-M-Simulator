"""Formato de lo que muestra la web de las corridas: identificadores, estados, escala y motor.

No toca la base ni los servicios: la web lo usa sobre lo que ya le regresaron (D36).
"""
from procesamiento.analitica import factor_de_escala, representados
from procesamiento.motor import AVISO_SIMULACION, ENGINE_VERSION  # noqa: F401
from procesamiento.motor.modelo import SIMPLIFICACIONES  # noqa: F401
from procesamiento.motores import de_version as motor_de_version

CLASE_BADGE_ESTADO = {
    "encolado": "badge-pendiente",
    "ejecutando": "badge-pendiente",
    "completado": "badge-correcto",
    "fallido": "badge-fallido",
    "cancelado": "badge-inactivo",
}


def id_simulacion(run_id):
    return f"SIM-{int(run_id):05d}"


def id_escenario(scenario_id):
    return f"ESC-{int(scenario_id):03d}"


def estado_visible(status_db):
    return (status_db or "").upper()


def clase_badge_estado(status_db):
    return CLASE_BADGE_ESTADO.get(status_db, "badge-inactivo")


def motor_de_resultado(engine_version):
    """(version actual, simplificaciones) del motor que produjo un resultado."""
    motor = motor_de_version(engine_version)
    if motor is None:
        return engine_version, []
    return motor.version, list(motor.simplificaciones)


def escala(habitantes, agentes, resumen=None):
    """El factor de escala de D6 y, con un resumen, sus conteos llevados a habitantes."""
    datos = factor_de_escala(habitantes, agentes)
    datos["representados"] = representados(resumen, datos) if resumen else {}
    return datos
