"""Validación de seir-ref contra resultados esperados (ficha del simulador, §13 a §15).

Las tablas completas, con más agentes y semillas, salen de
python -m procesamiento.mediciones esperados | sensibilidad | reproducibilidad.
"""
import copy

import pytest

from procesamiento import contrato, motores
from procesamiento.mediciones import _escala_tasa, escenario, r0_efectivo, tamano_final

SEIR = motores.IMPLEMENTADOS["seir-ref"].simular
AGENTES = 200_000
SEMILLAS = (1, 2, 3)


def ataque(esc):
    return sum(SEIR(copy.deepcopy(esc), s)["resumen"]["tasa_ataque"] for s in SEMILLAS) / len(SEMILLAS)


def media(esc, campo):
    return sum(SEIR(copy.deepcopy(esc), s)["resumen"][campo] for s in SEMILLAS) / len(SEMILLAS)


def test_tamano_final_conocido():
    assert tamano_final(2.0) == pytest.approx(0.7968, abs=1e-4)
    assert tamano_final(0.9) == 0.0


@pytest.mark.parametrize("r0", [1.3, 1.6, 2.5])
def test_el_ataque_es_el_tamano_final_de_un_seir_con_el_r0_efectivo(r0):
    esc = escenario(AGENTES, dias=365, r0=r0, intervenciones=False)
    efectivo = r0_efectivo(r0, esc["enfermedad"]["infeccioso_dias"]["valor"])
    assert ataque(esc) == pytest.approx(tamano_final(efectivo), abs=0.01)
    # Con el R0 nominal no coincide: el paso de un día alarga el periodo infeccioso (ficha, §13).
    assert ataque(esc) > tamano_final(r0) + 0.02


def test_bajo_el_umbral_no_hay_brote_y_se_cumple_la_ramificacion():
    # El total de una ramificación subcrítica varía mucho entre corridas: más casos iniciales y
    # más semillas (seir-ref tarda lo mismo con cualquier población).
    agentes = 1_000_000
    esc = escenario(agentes, dias=365, r0=0.8, intervenciones=False)
    esperado = esc["infectados_iniciales"] / agentes / (1 - r0_efectivo(0.8, 5.0))
    medido = sum(SEIR(copy.deepcopy(esc), s)["resumen"]["tasa_ataque"] for s in range(1, 6)) / 5
    assert medido == pytest.approx(esperado, rel=0.2) and medido < 0.01


def test_sin_letalidad_ni_hospitalizacion_no_hay_muertes_ni_hospitalizados():
    esc = escenario(AGENTES, dias=365, r0=2.5, intervenciones=False)
    _escala_tasa(esc, "letalidad", 0)
    _escala_tasa(esc, "tasa_hospitalizacion", 0)
    r = SEIR(esc, 1)["resumen"]
    assert r["fallecimientos"] == 0 and r["hospitalizaciones"] == 0


def _variado(nombre, factor):
    esc = escenario(AGENTES, dias=365, intervenciones=False)
    _escala_tasa(esc, nombre, factor)
    return esc


def test_sensibilidad_va_en_la_direccion_esperada():
    base = escenario(AGENTES, dias=365, intervenciones=False)
    assert ataque(_variado("r0", 1.2)) > ataque(base) > ataque(_variado("r0", 0.8))
    assert media(_variado("r0", 1.2), "dia_pico") < media(base, "dia_pico")
    assert media(_variado("incubacion_dias", 1.2), "dia_pico") > media(base, "dia_pico")
    assert ataque(_variado("incubacion_dias", 1.2)) == pytest.approx(ataque(base), abs=0.01)
    assert media(_variado("letalidad", 1.2), "fallecimientos") > media(base, "fallecimientos")
    assert ataque(_variado("letalidad", 1.2)) == pytest.approx(ataque(base), abs=0.01)


@pytest.mark.parametrize("nombre", ["seir-ref", "abm-ref"])
def test_misma_semilla_y_version_misma_corrida(nombre):
    motor = motores.IMPLEMENTADOS[nombre]
    una = motor.simular(copy.deepcopy(contrato.ESCENARIO_EJEMPLO), 7)
    otra = motor.simular(copy.deepcopy(contrato.ESCENARIO_EJEMPLO), 7)
    assert una == otra and una["engine_version"] == otra["engine_version"]
    assert motor.simular(copy.deepcopy(contrato.ESCENARIO_EJEMPLO), 8)["serie"] != una["serie"]
