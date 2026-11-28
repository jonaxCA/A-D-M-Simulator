from frontend_desktop.app import exportar, resumen


def datos_prueba():
    def escenario(nombre, dias, pesos):
        return {
            "nombre": nombre,
            "n": 1,
            "indicadores": {k: None for k, _ in resumen.INDICADORES},
            "costo": dias,
            "costo_pesos": pesos,
            "dominado_por": [],
            "curva": [],
        }

    return {
        "escenarios": [
            escenario("A", 100, 2000),
            escenario("B", 200, None),
        ],
        "semillas": [1],
        "metrica": "fallecimientos",
        "aviso": "No es una predicción.",
        "modelo_costo": "Supuesto de prueba",
        "trazabilidad_costos": [],
    }


def test_csv_separa_unidades():
    encabezados, filas = exportar.tabla_comparacion(datos_prueba())
    assert encabezados[-3:] == [
        "personas_dia", "costo_pesos_mxn", "frontera"
    ]
    assert filas[0][-3:] == [100, 2000, "No dominado"]
    assert filas[1][-3:] == [200, "Sin dato", "No dominado"]


def test_reporte_muestra_ambas_unidades():
    html = exportar.reporte_html(datos_prueba(), "Usuario prueba", [])
    assert "<th>Personas-día</th>" in html
    assert "<th>Costo (MXN)</th>" in html
    assert "$2,000.00" in html
    assert "Sin dato" in html
