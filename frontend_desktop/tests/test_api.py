import logging

import pytest

from frontend_desktop.app import api, config, xmlio

DIRECTORIO = (config.CONTRATOS / "estado-servicios/ejemplos/directorio_servicios.xml").read_bytes()
CORRIDA = (config.CONTRATOS / "corridas/ejemplos/consultar_corrida.xml").read_bytes()


class Respuesta:
    def __init__(self, status, contenido=b"", headers=None):
        self.status_code = status
        self.content = contenido
        self.headers = headers or {}


def problema(status, codigo, detalle="Algo falló."):
    return Respuesta(status, xmlio.escribir({"type": "about:blank", "title": "Error", "status": status,
                                            "detail": detalle, "codigo": codigo, "instance": "/x"}, "problem"))


def sesion(access, refresh):
    return Respuesta(200, xmlio.escribir({"access_token": access, "refresh_token": refresh,
                                          "token_type": "Bearer", "expires_in": 1200,
                                          "usuario": {"id": 5, "username": "alex.cavazos",
                                                      "roles": ["ANALISTA"]}}, "sesion"))


class HTTPFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def get(self, url, **_):
        return Respuesta(200, DIRECTORIO)

    def request(self, metodo, url, data=None, params=None, headers=None, timeout=None):
        self.llamadas.append((metodo, url, data, headers))
        return self.respuestas.pop(0)


def cliente(*respuestas):
    c = api.Cliente("http://directorio", HTTPFalso(respuestas))
    c.access, c.refresh = "acceso-viejo", "refresh-viejo"
    return c


def test_problem_xml_se_convierte_en_error():
    c = cliente(problema(404, "NO_ENCONTRADO", "No existe la corrida."))
    with pytest.raises(api.ErrorServicio) as error:
        c.pedir("corridas", "GET", "/api/v1/runs/9")
    assert (error.value.status, error.value.codigo, str(error.value)) == (404, "NO_ENCONTRADO", "No existe la corrida.")


def test_token_expirado_se_renueva_una_vez():
    c = cliente(problema(401, "TOKEN_EXPIRADO"), sesion("acceso-nuevo", "refresh-nuevo"), Respuesta(200, CORRIDA))
    assert c.pedir("corridas", "GET", "/api/v1/runs/43")["id"] == 43
    metodos = [(m, u.split("/api/v1/")[1]) for m, u, _, _ in c.http.llamadas]
    assert metodos == [("GET", "runs/43"), ("POST", "sessions/refresh"), ("GET", "runs/43")]
    assert c.http.llamadas[-1][3]["Authorization"] == "Bearer acceso-nuevo"
    assert (c.access, c.refresh) == ("acceso-nuevo", "refresh-nuevo")


def test_no_renueva_si_otro_hilo_ya_lo_hizo():
    c = cliente()
    c.access = "ya-renovado"
    c._renovar("acceso-viejo")
    assert c.http.llamadas == []


def test_token_revocado_cierra_la_sesion():
    c = cliente(problema(401, "TOKEN_REVOCADO"))
    with pytest.raises(api.SesionCerrada):
        c.pedir("corridas", "GET", "/api/v1/runs")
    assert c.access is None and c.refresh is None


def test_renovacion_rechazada_cierra_la_sesion():
    c = cliente(problema(401, "TOKEN_EXPIRADO"), problema(401, "TOKEN_REVOCADO"))
    with pytest.raises(api.SesionCerrada):
        c.pedir("corridas", "GET", "/api/v1/runs")
    assert c.access is None


def test_respuesta_que_no_cumple_su_xsd():
    c = cliente(Respuesta(200, b"<corrida><inventado>1</inventado></corrida>"))
    with pytest.raises(api.ErrorServicio) as error:
        c.pedir("corridas", "GET", "/api/v1/runs/1")
    assert "corrida.xsd" in str(error.value)


def test_sin_conexion():
    class Caido(HTTPFalso):
        def request(self, *a, **k):
            raise api.requests.ConnectionError()
    c = api.Cliente("http://directorio", Caido([]))
    with pytest.raises(api.ErrorServicio) as error:
        c.pedir("corridas", "GET", "/api/v1/runs")
    assert "No se pudo conectar con corridas" in str(error.value)


def test_la_bitacora_no_guarda_tokens_ni_contrasenas(caplog):
    c = api.Cliente("http://directorio", HTTPFalso([sesion("secreto-acceso", "secreto-refresh")]))
    with caplog.at_level(logging.INFO, logger="epidemia.escritorio"):
        c.iniciar_sesion("alex.cavazos", "Epidemia2026!", "abc", "12")
    assert c.roles() == ["ANALISTA"]
    assert "inició sesión" in caplog.text
    for secreto in ("secreto-acceso", "secreto-refresh", "Epidemia2026!"):
        assert secreto not in caplog.text
