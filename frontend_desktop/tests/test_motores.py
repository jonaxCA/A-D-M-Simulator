"""Bloque A: abm-gpu se ofrece al lanzar solo si corridas lo anuncia (D23, RF-H20, RF-E15)."""
from frontend_desktop.app import api, config, servicios, xmlio
from frontend_desktop.tests.test_api import Respuesta
from frontend_desktop.tests.test_mfa_reportes_datos import HTTP, ejemplo

DIRECTORIO = xmlio.escribir({"servicios": [{"nombre": "corridas", "url": "http://corridas"}]}, "directorio")


class HTTPCorridas(HTTP):
    def get(self, url, **_):
        return Respuesta(200, DIRECTORIO)


def cliente(*respuestas):
    c = api.Cliente("http://directorio", HTTPCorridas(*respuestas))
    c.access, c.refresh = "acceso", "renovacion"
    return c


def anuncio(motores):
    return xmlio.escribir({"total": len(motores), "referencia": "seir-ref", "motores": motores}, "motores")


def test_el_ejemplo_del_contrato_ofrece_lo_que_anuncia():
    c = cliente(Respuesta(200, ejemplo("corridas", "motores_habilitados")))
    assert servicios.motores_habilitados(c) == ["seir-ref", "abm-ref"]
    assert c.http.llamadas[0]["ruta"] == "runs/engines"


def test_abm_gpu_aparece_solo_si_el_servicio_lo_anuncia():
    c = cliente(Respuesta(200, anuncio(["seir-ref", "abm-ref", "abm-gpu"])))
    assert servicios.motores_habilitados(c) == ["seir-ref", "abm-ref", "abm-gpu"]
    assert "abm-gpu" not in config.MOTORES


def test_una_respuesta_que_no_cumple_el_xsd_deja_los_de_siempre():
    c = cliente(Respuesta(200, anuncio(["seir-ref", "otro"])))
    assert servicios.motores_habilitados(c) == list(config.MOTORES)


def test_si_corridas_no_responde_la_ruta_quedan_los_de_siempre():
    c = cliente(Respuesta(404, b""))
    assert servicios.motores_habilitados(c) == list(config.MOTORES)
