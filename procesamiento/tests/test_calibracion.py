import copy
import time
from datetime import date, timedelta

import numpy as np
import pytest

from procesamiento import contrato
from procesamiento.calibracion import (CalibracionCancelada, calibrar, configuracion_calibrada,
                                       evaluar, revisa_configuracion, revisa_parametros)
from procesamiento.calibracion.ajuste import metricas, perdida, ventanas
from procesamiento.calibracion.escenario import escenario_de_muestra, jornada
from procesamiento.calibracion.muestreo import hipercubo_latino
from procesamiento.calibracion.observacion import casos_semanales
from procesamiento.motor import simular

VERDAD = {"r0": 2.6, "rho": 0.3, "phi": 0.6}
SEMANAS = 18


def base():
    ejemplo = copy.deepcopy(contrato.ESCENARIO_EJEMPLO)
    return {"enfermedad": ejemplo["enfermedad"],
            "poblacion": {g: n * 100 for g, n in ejemplo["poblacion"].items()}}


def sintetica(theta=VERDAD, semilla=7):
    # Serie con parámetros conocidos y ruido de observación de Poisson: no es observada (D50).
    fechas = [str(date(2020, 3, 1) + timedelta(weeks=w)) for w in range(SEMANAS)]
    c0 = 20
    intervenciones = jornada(fechas[0], 7 * SEMANAS)
    escenario = escenario_de_muestra(base(), intervenciones, 7 * SEMANAS, c0, **theta)
    esperados = casos_semanales(simular(escenario, semilla)["serie"],
                                escenario["infectados_iniciales"], theta["rho"], SEMANAS)
    ruido = np.random.default_rng(semilla).poisson(esperados)
    ruido[0] = c0
    return [{"inicio": f, "valor": int(v)} for f, v in zip(fechas, ruido)]


@pytest.fixture(scope="module")
def calibrada():
    return calibrar(sintetica(), base(), {"muestras": 600, "semillas": 1, "cuantil": 0.05})


def test_recupera_los_parametros_de_una_serie_sintetica(calibrada):
    por_nombre = {p["nombre"]: p for p in calibrada["parametros"]}
    for nombre, valor in VERDAD.items():
        assert por_nombre[nombre]["p5"] <= valor <= por_nombre[nombre]["p95"], nombre
    assert calibrada["metricas"]["calibracion"]["r2"] > 0.9
    assert calibrada["metricas"]["validacion"]["cobertura"] >= 0.5


def test_el_resultado_registra_metodo_versiones_y_ventanas(calibrada):
    assert calibrada["metodo"] == "abc-rechazo"
    assert calibrada["version_metodo"] == "calibracion-0.1"
    assert calibrada["engine_version"] == "seir-ref-0.1"
    config = calibrada["configuracion"]
    assert config["ventanas"]["calibracion"]["semanas"] == 12
    assert config["ventanas"]["validacion"] == {"desde": "2020-05-24", "hasta": "2020-06-28",
                                                 "semanas": 6}
    assert config["semillas"] == [1]
    assert calibrada["perdida"]["aceptadas"] == len(calibrada["aceptadas"]) == 30
    assert calibrada["perdida"]["corridas"] == 600
    distancias = [a["distancia"] for a in calibrada["aceptadas"]]
    assert distancias == sorted(distancias)
    assert [s["ventana"] for s in calibrada["semanas"]].count("validacion") == 6
    assert len(calibrada["huella_configuracion"]) == 64


def test_la_misma_configuracion_da_el_mismo_resultado():
    observado, config = sintetica(), {"muestras": 100, "semillas": 1, "cuantil": 0.1}
    assert calibrar(observado, base(), config) == calibrar(observado, base(), config)
    otra = calibrar(observado, base(), dict(config, semilla_muestreo=2))
    assert otra["aceptadas"] != calibrar(observado, base(), config)["aceptadas"]


def test_cancelar_detiene_la_calibracion():
    avances = []
    with pytest.raises(CalibracionCancelada):
        calibrar(sintetica(), base(), {"muestras": 500, "semillas": 1, "cuantil": 0.02},
                 avance=avances.append, cancelada=lambda: len(avances) >= 1)
    assert avances == [40]


def test_evaluar_un_juego_de_parametros():
    resultado = evaluar(sintetica(), base(), VERDAD)
    assert resultado["semillas"] == [1, 2, 3, 4, 5]
    assert len(resultado["semanas"]) == SEMANAS
    assert resultado["metricas"]["calibracion"]["r2"] > 0.9
    with pytest.raises(ValueError):
        evaluar(sintetica(), base(), dict(VERDAD, rho=0))


def test_configuracion_calibrada_da_la_entrada_de_una_version(calibrada):
    entrada = configuracion_calibrada(calibrada)
    rho = next(p for p in calibrada["parametros"] if p["nombre"] == "rho")["mediana"]
    assert entrada["horizon_days"] == 7 * SEMANAS
    assert entrada["initial_infected"] == max(1, round(20 / rho))
    assert [iv["code"] for iv in entrada["interventions"]] == [
        "CIERRE_ESCUELAS", "CIERRE_TRABAJO", "REDUCCION_AFORO"]
    assert [iv["start_day"] for iv in entrada["interventions"]] == [22, 29, 22]
    assert entrada["interventions"][0]["params"] == {"reduccion": 1.0}


def test_el_hipercubo_cubre_cada_estrato_una_vez():
    puntos = hipercubo_latino(50, {"a": (0.0, 1.0), "b": (10.0, 20.0)}, 3)
    assert sorted(np.floor(puntos["a"] * 50).astype(int)) == list(range(50))
    assert sorted(np.floor((puntos["b"] - 10) / 10 * 50).astype(int)) == list(range(50))
    assert np.array_equal(puntos["a"], hipercubo_latino(50, {"a": (0.0, 1.0)}, 3)["a"])


def test_perdida_y_metricas():
    assert perdida(np.array([0, np.e - 1]), np.array([0, 0])) == pytest.approx(1.0)
    m = metricas([10, 20, 30], [10, 20, 33], [9, 21, 25], [11, 25, 35])
    assert m["rmse"] == pytest.approx(3 / np.sqrt(3))
    assert m["r2"] == pytest.approx(1 - 9 / 200)
    assert m["cobertura"] == pytest.approx(2 / 3)
    assert metricas([5, 5], [5, 6], [0, 0], [9, 9])["r2"] is None


def test_ventanas_dos_tercios_calibran():
    assert ventanas(22) == (15, 7)
    assert ventanas(18) == (12, 6)
    assert ventanas(6) == (4, 2)


def test_casos_semanales_desfasa_cinco_dias():
    serie = [{"nuevos_casos": 0}] + [{"nuevos_casos": 10}] * 13
    semanas = casos_semanales(serie, infectados_iniciales=4, rho=0.5, semanas=2)
    # Semana 0: los 4 iniciales y los contagios del día 1 (síntomas el día 6).
    # Semana 1: los contagios de los días 2 a 8.
    assert list(semanas) == [0.5 * (4 + 10), 0.5 * 70]


def test_la_jornada_en_dias_desde_el_inicio_de_la_ventana():
    assert [(iv["tipo"], iv["dia_inicio"]) for iv in jornada("2020-03-01", 154)] == [
        ("CIERRE_ESCUELAS", 22), ("CIERRE_TRABAJO", 29), ("REDUCCION_AFORO", 22)]
    assert jornada("2020-03-29", 70)[0]["dia_inicio"] == 0
    assert jornada("2019-01-06", 70) == []


def test_revisa_la_configuracion_y_los_parametros():
    assert revisa_configuracion({"muestras": 5000, "semillas": 3, "cuantil": 0.01,
                                 "semilla_muestreo": 1}) == []
    assert revisa_configuracion({"muestras": 20000, "semillas": 3, "cuantil": 0.01,
                                 "semilla_muestreo": 1})
    assert revisa_configuracion({"muestras": 100, "semillas": 1, "cuantil": 0.05,
                                 "semilla_muestreo": 1})
    assert revisa_parametros(VERDAD) == []
    assert revisa_parametros({"r0": 6, "rho": 0.5, "phi": 0.5}) == ["r0 debe estar entre 1.0 y 5.0."]
    with pytest.raises(ValueError):
        calibrar(sintetica()[:5], base(), {"muestras": 100, "semillas": 1, "cuantil": 0.1})


def test_una_corrida_de_seir_ref_tarda_poco():
    # 5 000 muestras con 3 semillas son 15 000 corridas: deben caber en minutos (D50).
    escenario = escenario_de_muestra(base(), jornada("2020-03-01", 154), 154, 7, **VERDAD)
    inicio = time.perf_counter()
    for semilla in range(20):
        simular(escenario, semilla)
    assert (time.perf_counter() - inicio) / 20 < 0.1
