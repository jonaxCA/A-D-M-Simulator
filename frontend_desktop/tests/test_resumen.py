from frontend_desktop.app import resumen


def test_una_corrida_por_semilla_la_mas_reciente():
    corridas = [{"id": 1, "seed": 1}, {"id": 5, "seed": 1}, {"id": 3, "seed": 2}]
    assert {s: c["id"] for s, c in resumen.una_por_semilla(corridas).items()} == {1: 5, 2: 3}


def test_semillas_comunes():
    assert resumen.semillas_comunes({10: {1: {}, 2: {}, 3: {}}, 11: {2: {}, 3: {}, 4: {}}}) == [2, 3]
    assert resumen.semillas_comunes({}) == []


def test_estadisticas():
    e = resumen.estadisticas(range(1, 22))
    assert (e["n"], e["media"], e["mediana"], e["p5"], e["p95"]) == (21, 11, 11, 2, 20)
    assert resumen.estadisticas([7])["p5"] == resumen.estadisticas([7])["p95"] == 7
    assert resumen.estadisticas([None]) is None


def test_curva_mediana_y_banda():
    series = [[{"dia": 0, "casos_activos": v}, {"dia": 1, "casos_activos": v * 2}] for v in (1, 2, 3)]
    assert resumen.curva(series)[1] == {"dia": 1, "mediana": 4, "p5": 2.2, "p95": 5.8}


def esc(nombre, costo, mediana):
    return {"nombre": nombre, "costo": costo, "impacto": {"mediana": mediana}}


def test_frontera_sobre_medianas():
    escenarios = resumen.marcar_frontera([esc("base", 0, 100), esc("caro", 50, 100), esc("bueno", 20, 60),
                                          esc("sin costo", None, 10)])
    assert [e["dominado_por"] for e in escenarios] == [[], ["base", "bueno"], [], None]


def test_armar():
    elegidas = {7: [{"id": 1, "seed": 1, "scenario_name": "A", "version_number": 2},
                    {"id": 2, "seed": 2, "scenario_name": "A", "version_number": 2}],
                8: [{"id": 3, "seed": 1, "scenario_name": "B", "version_number": 1},
                    {"id": 4, "seed": 2, "scenario_name": "B", "version_number": 1}]}
    serie = [{"dia": 0, "casos_activos": 10}]
    comparadas = [{"id": i, "serie": serie, "fallecimientos": f, "pico_casos_activos": 5, "dia_pico": 3,
                   "tasa_ataque": 0.5} for i, f in ((1, 10), (2, 20), (3, 4), (4, 6))]
    pareto = {"filas": [{"id": i, "costo": c} for i, c in ((1, 0), (2, 0), (3, 100), (4, 100))],
              "modelo_costo": "unitario", "aviso": "No es predicción"}
    datos = resumen.armar(elegidas, comparadas, pareto, "fallecimientos", "")
    a, b = datos["escenarios"]
    assert (a["nombre"], a["n"], a["impacto"]["mediana"], a["costo"]) == ("A · v2", 2, 15, 0)
    assert b["indicadores"]["fallecimientos"]["media"] == 5
    assert a["dominado_por"] == [] and b["dominado_por"] == []
    assert datos["aviso"] == "No es predicción" and datos["semillas"] == [1, 2]
