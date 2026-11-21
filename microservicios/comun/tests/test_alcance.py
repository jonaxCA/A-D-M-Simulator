import pytest

from epidemia_comun import alcance
from epidemia_comun.errores import ErrorAPI


class Respuesta:
    def __init__(self, estado, cuerpo=None):
        self.status_code, self.cuerpo = estado, cuerpo

    def json(self):
        return self.cuerpo


def responde(monkeypatch, respuesta):
    monkeypatch.setattr(alcance, "llamar", lambda *a, **k: respuesta)


def test_sin_alcance_la_cuenta_es_nacional(monkeypatch):
    responde(monkeypatch, Respuesta(200, {"nacional": True, "regiones_cubiertas": []}))
    assert alcance.regiones_permitidas() is None
    alcance.exige_region(99)


def test_con_alcance_solo_pasan_las_regiones_cubiertas(monkeypatch):
    responde(monkeypatch, Respuesta(200, {"nacional": False, "regiones_cubiertas": [9, 10]}))
    assert alcance.regiones_permitidas() == {9, 10}
    alcance.exige_region(10)
    with pytest.raises(ErrorAPI) as error:
        alcance.exige_region(11)
    assert error.value.estado == 403


def test_con_alcance_solo_por_institucion_no_limita_las_regiones(monkeypatch):
    responde(monkeypatch, Respuesta(200, {"nacional": False, "region_ids": [], "regiones_cubiertas": [],
                                          "institution_ids": [1]}))
    assert alcance.regiones_permitidas() is None
    alcance.exige_region(9)


def test_nacional_no_consulta_la_region(monkeypatch):
    responde(monkeypatch, Respuesta(200, {"nacional": True, "regiones_cubiertas": []}))
    alcance.exige_region_de(lambda: pytest.fail("no debía consultarla"))
    responde(monkeypatch, Respuesta(200, {"nacional": False, "regiones_cubiertas": [9]}))
    alcance.exige_region_de(lambda: None)
    with pytest.raises(ErrorAPI):
        alcance.exige_region_de(lambda: 10)


def test_si_roles_falla_no_se_deja_pasar(monkeypatch):
    responde(monkeypatch, Respuesta(500))
    with pytest.raises(ErrorAPI) as error:
        alcance.regiones_permitidas()
    assert error.value.estado == 503 and error.value.codigo == "SERVICIO_NO_DISPONIBLE"
