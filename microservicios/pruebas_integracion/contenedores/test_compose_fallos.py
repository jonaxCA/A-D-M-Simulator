"""Caídas de un servicio, de PostgreSQL y un timeout (N5); la de Redis está en test_compose_redis.py.
La demostración para humanos es infra/demo_fallos.py."""
from microservicios.estado_servicios.sondeo import SERVICIOS

from .conftest import espera


def test_servicio_caido_no_tumba_a_los_demas(api, sesion, compose):
    admin = sesion("admin")
    compose("stop", "casos")
    try:
        assert api("regiones", "GET", "/api/v1/regions").status_code == 200
        espera(lambda: next(s for s in api("estado-servicios", "GET", "/api/v1/services/health").json()["servicios"]
                            if s["nombre"] == "casos")["estado"] == "caido", 90, "El panel no marcó casos como caído.", cada=3)
    finally:
        compose("start", "casos")
    espera(lambda: api("casos", "GET", "/api/v1/cases", admin["access"]).status_code == 200, 60,
           "casos no volvió.", cada=2)
    espera(lambda: api("estado-servicios", "GET", "/api/v1/services/health").json()["resumen"]["ok"] == len(SERVICIOS),
           60, "No volvieron todos a ok.", cada=3)


def test_postgres_apagado_y_encendido(api, sesion, compose):
    admin = sesion("admin")
    compose("stop", "postgres")
    try:
        assert api("casos", "GET", "/health").status_code == 503
        assert api("casos", "GET", "/api/v1/cases", admin["access"]).status_code >= 500
    finally:
        compose("start", "postgres")
    espera(lambda: api("casos", "GET", "/api/v1/cases", admin["access"]).status_code == 200, 120,
           "casos no volvió con PostgreSQL.", cada=3)


def test_timeout_con_servicio_pausado(api, sesion, compose, catalogo):
    analista = sesion("analista")
    cuerpo = {"name": "Timeout prueba", "description": "N5", "disease_id": catalogo["disease_id"],
              "region_id": catalogo["region_id"], "population_size": catalogo["poblacion"], "horizon_days": 90,
              "initial_infected": 10, "stratify": False, "notes": None}
    compose("pause", "validacion")
    try:
        r = api("escenarios", "POST", "/api/v1/scenarios", analista["access"], json=cuerpo, timeout=30)
        assert r.status_code == 503 and r.json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
    finally:
        compose("unpause", "validacion")
    espera(lambda: api("escenarios", "GET", "/api/v1/scenarios", analista["access"]).status_code == 200, 60,
           "escenarios no volvió.")
