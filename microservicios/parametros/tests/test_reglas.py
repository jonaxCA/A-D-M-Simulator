import pytest

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import de_xml
from microservicios.parametros.reglas import parametros_epidemiologicos

# Los límites son los del motor (procesamiento.entrada_motor.PARAMETROS_SIMULACION): R0 de 0.01 a
# 20 y las tasas, de 0 a 1.


def test_parametro_valido():
    out = parametros_epidemiologicos({"r0": {"valor": 1.7, "fuente": "Estudio 2025", "supuesto": False}})
    assert out["r0"] == {"valor": 1.7, "fuente": "Estudio 2025", "supuesto": False}


def test_parametro_con_supuesto():
    assert parametros_epidemiologicos({"r0": {"valor": 2, "supuesto": True}})["r0"]["supuesto"] is True


@pytest.mark.parametrize("valor", [False, "mal", float("inf"), {}, 50])
def test_parametro_no_valido(valor):
    with pytest.raises(ErrorAPI):
        parametros_epidemiologicos({"r0": {"valor": valor, "fuente": "Fuente"}})


def test_exige_fuente_o_supuesto():
    with pytest.raises(ErrorAPI) as exc:
        parametros_epidemiologicos({"r0": {"valor": 2.3}})
    assert exc.value.estado == 422


def test_no_borra_los_demas_y_none_borra_uno():
    out = parametros_epidemiologicos({"r0": {"valor": 2.5, "supuesto": True}, "letalidad": None},
                                     {"letalidad_por_edad": {"0-19": 0.001}, "letalidad": {"valor": 0.1}})
    assert out["letalidad_por_edad"]["0-19"] == 0.001 and "letalidad" not in out


def test_tasa_como_fraccion():
    assert parametros_epidemiologicos({"tasa_hospitalizacion": {"valor": 0.25, "supuesto": True}})[
        "tasa_hospitalizacion"]["valor"] == 0.25
    with pytest.raises(ErrorAPI):
        parametros_epidemiologicos({"tasa_hospitalizacion": {"valor": 25, "supuesto": True}})


def test_xml_sin_atributos_de_tipo():
    documento = (b"<parametros><r0><valor>1.5</valor><fuente>Estudio</fuente><supuesto>false</supuesto>"
                 b"<intervalo><min>1.2</min><max>1.9</max><tipo>IC95</tipo></intervalo></r0></parametros>")
    out = parametros_epidemiologicos(de_xml(documento))
    assert out["r0"] == {"valor": 1.5, "fuente": "Estudio", "supuesto": False,
                         "intervalo": {"min": 1.2, "max": 1.9, "tipo": "IC95"}}


def test_el_intervalo_es_opcional_y_por_omision_es_un_rango():
    out = parametros_epidemiologicos({"letalidad": {"valor": 0.005, "fuente": "Salje 2020",
                                                    "intervalo": {"min": 0.003, "max": 0.009}}})
    assert out["letalidad"]["intervalo"] == {"min": 0.003, "max": 0.009, "tipo": "rango"}
    assert "intervalo" not in parametros_epidemiologicos({"r0": {"valor": 2, "supuesto": True}})["r0"]


@pytest.mark.parametrize("intervalo,mensaje", [
    ({"min": 2.5, "max": 3.0}, "contener el valor"),        # no contiene 2.0
    ({"min": 1.0, "max": 25.0}, "caber en el rango"),        # pasa el máximo de R0
    ({"min": 1.0}, "min, max"),
    ({"min": 1.0, "max": 3.0, "nivel": 95}, "min, max"),
    ({"min": "uno", "max": 3.0}, "números finitos"),
    ({"min": 1.0, "max": 3.0, "tipo": "IC90"}, "tipo de intervalo"),
    ([1.0, 3.0], "min, max"),
])
def test_un_intervalo_invalido_es_422(intervalo, mensaje):
    with pytest.raises(ErrorAPI) as exc:
        parametros_epidemiologicos({"r0": {"valor": 2.0, "fuente": "F", "intervalo": intervalo}})
    assert exc.value.estado == 422 and mensaje in exc.value.detalle
