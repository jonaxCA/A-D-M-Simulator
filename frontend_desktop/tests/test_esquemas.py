from xml.etree import ElementTree as ET

import pytest

from frontend_desktop.app import config, esquemas


def ejemplos_validables():
    for (servicio, raiz), xsd in esquemas.POR_RESPUESTA.items():
        carpeta = config.CONTRATOS / xsd.split("/")[0] / "ejemplos"
        for archivo in sorted(carpeta.glob("*.xml")):
            if "peticion" not in archivo.name and ET.parse(archivo).getroot().tag == raiz:
                yield servicio, archivo


@pytest.mark.parametrize("servicio,archivo", list(ejemplos_validables()), ids=lambda x: getattr(x, "name", x))
def test_ejemplos_validan_con_su_xsd(servicio, archivo):
    contenido = archivo.read_bytes()
    esquemas.validar_con(esquemas.xsd_de(servicio, ET.fromstring(contenido).tag), contenido)


def test_errores_de_ejemplo_validan_como_problem():
    for archivo in sorted(config.CONTRATOS.glob("*/ejemplos/*.xml")):
        if ET.parse(archivo).getroot().tag == "problem":
            esquemas.validar_con(esquemas.PROBLEMA, archivo.read_bytes())


def test_escenario_alterado_no_pasa():
    original = (config.CONTRATOS / "escenarios-xml/ejemplos/exportar_escenario.xml").read_bytes()
    esquemas.validar_escenario(original)
    with pytest.raises(esquemas.XMLInvalido) as error:
        esquemas.validar_escenario(original.replace(b"<cobertura>0.800", b"<cobertura>1.500"))
    assert "cobertura" in error.value.errores[0]["ruta"]


def test_respuesta_sin_xsd_no_se_valida():
    assert esquemas.xsd_de("escenarios", "lista_escenarios") is None
