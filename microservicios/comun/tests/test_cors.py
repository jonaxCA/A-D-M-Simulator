"""CORS de crear_app: abierto solo para el origen de la consola (CONSOLE_ORIGIN)."""
import pytest

CONSOLA = "http://localhost:5260"


@pytest.fixture
def con_consola(crear_cliente, monkeypatch):
    def crear(paquete):
        cliente = crear_cliente(paquete)
        monkeypatch.setitem(cliente.application.config, "CONSOLE_ORIGIN", CONSOLA)
        return cliente
    return crear


def test_la_consola_puede_leer_la_respuesta_y_su_correlation_id(con_consola):
    r = con_consola("estado_servicios").get("/api/v1/services?format=json",
                                            headers={"Origin": CONSOLA})
    assert r.status_code == 200
    assert r.headers["Access-Control-Allow-Origin"] == CONSOLA
    assert r.headers["Access-Control-Expose-Headers"] == "X-Correlation-ID"
    assert r.headers["X-Correlation-ID"]


def test_otro_origen_no_recibe_cors(con_consola):
    r = con_consola("zonas").get("/openapi.json", headers={"Origin": "http://127.0.0.1:5260"})
    assert "Access-Control-Allow-Origin" not in r.headers


def test_sin_consola_configurada_no_hay_cors(crear_cliente):
    cliente = crear_cliente("zonas")
    assert not cliente.application.config.get("CONSOLE_ORIGIN")
    r = cliente.get("/openapi.json", headers={"Origin": CONSOLA})
    assert "Access-Control-Allow-Origin" not in r.headers


def test_la_consulta_previa_de_una_ruta_protegida_no_pide_token(con_consola):
    # El navegador manda OPTIONS sin Authorization antes de un GET que sí lo lleva.
    r = con_consola("zonas").open("/api/v1/zones", method="OPTIONS", headers={
        "Origin": CONSOLA, "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization"})
    assert r.status_code == 200
    assert r.headers["Access-Control-Allow-Origin"] == CONSOLA
    assert "Authorization" in r.headers["Access-Control-Allow-Headers"]
