"""F7 en los contenedores: la serie agregada contra PostgreSQL real coincide con la curva de
siempre, por día, por semana, por grupo y en Highcharts."""
import uuid


def test_la_serie_agregada_coincide_con_la_curva(api, sesion, catalogo, base, analista):
    karla = sesion("capturista")
    conexion = base()
    with conexion.cursor() as cur:
        cur.execute("SELECT current_date::text")
        hoy = cur.fetchone()[0]
    conexion.close()
    for sexo in ("F", "M", "F"):
        r = api("casos", "POST", "/api/v1/cases", karla["access"], json={
            "local_uuid": str(uuid.uuid4()), "disease_id": catalogo["disease_id"],
            "region_id": catalogo["region_id"], "report_date": hoy, "sex": sexo, "age": 30})
        assert r.status_code == 201, r.text
    token = analista["access"]
    filtros = {"days": 30, "disease_id": catalogo["disease_id"]}
    curva = {p["fecha"]: p["casos"]
             for p in api("series", "GET", "/api/v1/series/cases", token, params=filtros).json()["puntos"]}

    por_dia = api("series", "GET", "/api/v1/series/cases/aggregate", token,
                  params=dict(filtros, size=30, group_by="sexo")).json()
    assert por_dia["total"] == 30 and por_dia["filtros"]["hasta"] == hoy
    assert {p["inicio"]: p["casos"] for p in por_dia["periodos"] if p["casos"]} == curva
    assert por_dia["total_casos"] == sum(curva.values()) >= 3
    for p in por_dia["periodos"]:
        assert sum(g["casos"] for g in p["por_grupo"]) == p["casos"]
    assert {"Femenino", "Masculino"} <= set(por_dia["grupos"])

    por_semana = api("series", "GET", "/api/v1/series/cases/aggregate", token,
                     params=dict(filtros, interval="semana")).json()
    assert por_semana["total_casos"] == por_dia["total_casos"]
    assert all(p["semana_epi"] for p in por_semana["periodos"])

    graficas = api("series", "GET", "/api/v1/series/cases/highcharts", token,
                   params=dict(filtros, interval="mes", group_by="edad")).json()
    assert sum(punto["y"] for s in graficas["series"] for punto in s["data"]) == por_dia["total_casos"]
    assert [s["name"] for s in graficas["series"]][:6] == ["0-4", "5-14", "15-24", "25-44", "45-64", "65+"]
