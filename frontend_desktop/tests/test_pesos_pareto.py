from frontend_desktop.app import resumen


def test_personas_dia_y_pesos_separados():
    elegidas = {
        1: [
            {"id": i, "seed": s, "scenario_name": "A", "version_number": 1}
            for i, s in [(11, 1), (12, 2)]
        ],
        2: [
            {"id": i, "seed": s, "scenario_name": "B", "version_number": 1}
            for i, s in [(21, 1), (22, 2)]
        ],
    }
    comparadas = [
        {"id": i, "fallecimientos": f,
         "serie": [{"dia": 0, "casos_activos": f}]}
        for i, f in [(11, 20), (12, 30), (21, 10), (22, 15)]
    ]
    pareto = {"filas": [
        {"id": 11, "costo": 100, "costo_pesos": 1000},
        {"id": 12, "costo": 200, "costo_pesos": 3000},
        {"id": 21, "costo": 300, "costo_pesos": None},
        {"id": 22, "costo": 400, "costo_pesos": 8000},
    ]}
    datos = resumen.armar(
        elegidas, comparadas, pareto, "fallecimientos", "Aviso"
    )
    a, b = datos["escenarios"]
    assert a["costo"] == 150
    assert a["costo_pesos"] == 2000
    assert b["costo"] == 350
    assert b["costo_pesos"] is None
