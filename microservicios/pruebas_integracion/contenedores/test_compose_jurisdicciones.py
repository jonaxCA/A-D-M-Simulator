"""F7 en los contenedores: las jurisdicciones sanitarias contra PostgreSQL real suman lo mismo
que la tabla por zona, y la imagen de zonas trae el archivo que las define."""


def test_las_jurisdicciones_suman_lo_mismo_que_los_municipios(api, analista):
    token = analista["access"]
    filtros = {"days": 90}
    municipios = {z["zona"]: z for z in api("zonas", "GET", "/api/v1/zones", token,
                                            params=dict(filtros, size=100)).json()["zonas"]}
    assert len(municipios) == 51
    datos = api("zonas", "GET", "/api/v1/zones/jurisdictions", token, params=filtros).json()
    grupos = {g["clave"]: g for g in datos["jurisdicciones"]}
    assert list(grupos) == ["compartido-19039", "2", "3", "4", "5", "6", "7", "8"]
    assert sum(len(g["municipios"]) for g in grupos.values()) == 51
    assert sum(g["casos"] for g in grupos.values()) == sum(z["casos"] for z in municipios.values())
    assert sum(g["graves"] for g in grupos.values()) == sum(z["graves"] for z in municipios.values())
    # Por clave INEGI y con los nombres que da la propia base, no escritos a mano.
    cuatro = grupos["4"]
    assert {m["region_code"] for m in cuatro["municipios"]} == {"19006", "19026", "19031"}
    assert cuatro["casos"] == sum(municipios[m["nombre"]]["casos"] for m in cuatro["municipios"])
    assert grupos["compartido-19039"]["casos"] == municipios["Monterrey"]["casos"]
    assert "artículo 27" in datos["fuente"]["documento"]
