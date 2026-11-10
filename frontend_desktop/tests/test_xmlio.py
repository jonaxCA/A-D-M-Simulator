import pytest

from frontend_desktop.app import config, xmlio

EJEMPLOS = sorted(config.CONTRATOS.glob("*/ejemplos/*.xml"))


def ejemplo(ruta):
    return (config.CONTRATOS / ruta).read_bytes()


@pytest.mark.parametrize("archivo", EJEMPLOS, ids=lambda a: "%s/%s" % (a.parent.parent.name, a.name))
def test_todos_los_ejemplos_se_leen(archivo):
    assert isinstance(xmlio.leer(archivo.read_bytes()), dict)


def test_lista_con_un_elemento_sigue_siendo_lista():
    datos = xmlio.leer(ejemplo("escenarios/ejemplos/listar_escenarios.xml"))
    assert isinstance(datos["escenarios"], list) and len(datos["escenarios"]) == 1
    assert datos["escenarios"][0]["population_size"] == 1142994


def test_listas_vacias_y_de_item():
    datos = xmlio.leer(ejemplo("validacion/ejemplos/validar_version.xml"))
    assert datos["errores"] == [] and datos["avisos"] == [] and datos["valido"] is True
    invalido = xmlio.leer(ejemplo("validacion/ejemplos/validar_escenario_invalido.xml"))
    assert invalido["errores"] == ["Los infectados iniciales no pueden superar la población."]


def test_tipos_numero_nulo_y_frontera():
    datos = xmlio.leer(ejemplo("pareto/ejemplos/comparar_costo_impacto.xml"))
    assert datos["base"] is None
    assert datos["frontera"] == [12, 14, 13, 15]
    assert datos["filas"][0]["desglose_costo"] == []
    assert datos["filas"][1]["costo"] == 292500000


def test_esquema_de_parametros():
    tipos = xmlio.leer(ejemplo("tipos-intervencion/ejemplos/listar_tipos_intervencion.xml"))["tipos"]
    vacuna = next(t for t in tipos if t["code"] == "VACUNACION")
    assert vacuna["param_schema"]["required"] == ["eficacia", "dosis_diarias"]
    assert vacuna["param_schema"]["properties"]["prioridad"]["enum"][0] == "edad_desc"


def test_ida_y_vuelta():
    datos = {"code": "VACUNACION", "start_day": 20, "end_day": None, "coverage": 0.6,
             "activa": True, "params": {"eficacia": 0.7}, "por_edad": {"0-19": 3}}
    assert xmlio.leer(xmlio.escribir(datos, "intervencion")) == datos


def test_no_acepta_entidades_externas():
    malicioso = b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><a>&x;</a>'
    with pytest.raises(Exception):
        xmlio.leer(malicioso)
