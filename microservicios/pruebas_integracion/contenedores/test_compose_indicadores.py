"""F7 en los contenedores: la consulta de `indicadores` contra PostgreSQL real, y que cada
indicador explicado coincida con los campos de siempre del tablero."""
import uuid

import redis

from epidemia_comun import llaves


def test_cada_indicador_con_su_cuenta_coincide_con_el_tablero(api, sesion, catalogo, base, entorno):
    karla = sesion("capturista")
    conexion = base()
    with conexion.cursor() as cur:
        cur.execute("SELECT current_date::text")
        hoy = cur.fetchone()[0]
    conexion.close()
    for gravedad in ("fallecido", "grave", "leve"):
        r = api("casos", "POST", "/api/v1/cases", karla["access"], json={
            "local_uuid": str(uuid.uuid4()), "disease_id": catalogo["disease_id"],
            "region_id": catalogo["region_id"], "report_date": hoy, "severity": gravedad})
        assert r.status_code == 201, r.text
    # Sin la caché de 60 s, para ver los casos recién creados.
    redis.Redis(host="127.0.0.1", port=int(entorno["REDIS_PUERTO_LOCAL"]),
                password=entorno["REDIS_PASSWORD"]).delete(llaves.cache("indicadores", "indicators"))

    tablero = api("indicadores", "GET", "/api/v1/dashboard/indicators").json()
    ind = {i["clave"]: i for i in tablero["indicadores"]}
    assert ind["casos_activos"]["valor"] == tablero["casos_activos"] >= 3
    assert ind["casos_activos"]["variacion_pct"] == tablero["casos_pct"]
    assert ind["tasa_incidencia"]["valor"] == tablero["tasa_incidencia"]
    assert ind["tasa_incidencia"]["variacion_pct"] == tablero["tasa_pct"]
    assert ind["zonas_en_riesgo"]["valor"] == tablero["zonas_en_riesgo"]
    assert ind["simulaciones_activas"]["valor"] == tablero["simulaciones_activas"]
    assert ind["tasa_incidencia"]["periodo"]["hasta"] == hoy

    casos = ind["casos_activos"]["numerador"]["valor"]
    fallecidos = ind["tasa_mortalidad"]["numerador"]["valor"]
    graves = ind["casos_graves"]["numerador"]["valor"]
    assert fallecidos >= 1 and graves >= 1
    assert ind["letalidad"]["valor"] == round(fallecidos / casos * 100, 1)
    assert ind["casos_graves"]["valor"] == round(graves / casos * 100, 1)
    assert ind["zonas_en_riesgo"]["denominador"]["valor"] == 51


def test_la_imagen_trae_las_camas_censables_y_la_capacidad_su_fuente(api):
    """D57: la imagen de indicadores copia datos/capacidad/camas_censables_nl.csv (lo deja pasar
    .dockerignore). Sin él, capacidad_utilizada saldría sin denominador."""
    ind = {i["clave"]: i for i in api("indicadores", "GET", "/api/v1/dashboard/indicators").json()["indicadores"]}
    capacidad = ind["capacidad_utilizada"]
    assert capacidad["denominador"]["valor"] == 4339
    assert capacidad["fuente"]["corte"] == "2025-12-31" and len(capacidad["fuente"]["sha256"]) == 64
    assert capacidad["numerador"]["valor"] == ind["hospitalizaciones"]["valor"]
    assert capacidad["valor"] == round(capacidad["numerador"]["valor"] / 4339 * 100, 1)
    assert ind["prevalencia"]["periodo"]["dias"] == 14
