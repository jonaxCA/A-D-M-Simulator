"""Redis apagado y encendido a mitad de la prueba: lo protegido responde 503, los catálogos siguen,
y al volver Redis todo regresa con la misma sesión y sin reiniciar servicios."""
from microservicios.estado_servicios.sondeo import SERVICIOS

from .conftest import espera


def test_redis_apagado_y_encendido(api, sesion, compose):
    admin = sesion("admin")
    assert api("casos", "GET", "/api/v1/cases", admin["access"]).status_code == 200
    compose("stop", "redis")
    try:
        protegida = api("casos", "GET", "/api/v1/cases", admin["access"])
        assert protegida.status_code == 503 and protegida.json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
        assert api("regiones", "GET", "/api/v1/regions").status_code == 200
    finally:
        compose("start", "redis")
    espera(lambda: api("casos", "GET", "/api/v1/cases", admin["access"]).status_code == 200, 60,
           "casos no volvió a responder con la misma sesión.", cada=2)
    espera(lambda: api("estado-servicios", "GET", "/api/v1/services/health").json()["resumen"]["ok"] == len(SERVICIOS),
           60, "No volvieron todos a ok.", cada=3)
