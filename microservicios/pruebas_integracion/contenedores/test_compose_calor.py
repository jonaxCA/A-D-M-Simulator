"""F7 en los contenedores: el mapa de calor contra PostgreSQL real agrega los casos en celdas y
no publica una celda con menos de 3."""
import uuid


def test_mapa_de_calor_agrega_y_suprime(api, sesion, catalogo, base, analista):
    karla = sesion("capturista")
    conexion = base()
    with conexion.cursor() as cur:
        cur.execute("SELECT current_date::text")
        hoy = cur.fetchone()[0]
    conexion.close()
    # Tres casos en la misma celda de 0.01° de Monterrey y uno solo en otra.
    for lat, lon in ((25.70123, -100.34456), (25.70456, -100.34789), (25.70999, -100.34001),
                     (25.75555, -100.30555)):
        r = api("casos", "POST", "/api/v1/cases", karla["access"], json={
            "local_uuid": str(uuid.uuid4()), "disease_id": catalogo["disease_id"],
            "region_id": catalogo["region_id"], "report_date": hoy,
            "latitude": lat, "longitude": lon})
        assert r.status_code == 201, r.text

    datos = api("zonas", "GET", "/api/v1/zones/heatmap", analista["access"],
                params={"days": 7, "disease_id": catalogo["disease_id"]}).json()
    celda = next(p for p in datos["puntos"] if (p["lat"], p["lon"]) == (25.705, -100.345))
    assert celda["casos"] >= 3
    assert not any((p["lat"], p["lon"]) == (25.755, -100.305) for p in datos["puntos"])
    assert datos["casos_suprimidos"] >= 1 and datos["celdas_suprimidas"] >= 1
    assert datos["total_casos"] == (datos["casos_en_puntos"] + datos["casos_suprimidos"]
                                    + datos["casos_sin_coordenadas"])
    assert sum(p["casos"] for p in datos["puntos"]) == datos["casos_en_puntos"]
