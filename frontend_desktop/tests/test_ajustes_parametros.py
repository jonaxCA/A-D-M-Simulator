"""Bloque A: ajustar los parámetros de una versión de escenario (D59, A4 «Configuración del modelo»)."""
import os

import pytest

from frontend_desktop.app import api, config, servicios, xmlio
from frontend_desktop.tests.test_api import Respuesta, problema
from frontend_desktop.tests.test_mfa_reportes_datos import HTTP, ejemplo

DIRECTORIO = xmlio.escribir({"servicios": [{"nombre": "parametros", "url": "http://parametros"}]}, "directorio")


class HTTPParametros(HTTP):
    def get(self, url, **_):
        return Respuesta(200, DIRECTORIO)


def cliente(*respuestas):
    c = api.Cliente("http://directorio", HTTPParametros(*respuestas))
    c.access, c.refresh = "acceso", "renovacion"
    return c


def test_lee_los_ajustes_de_la_version_con_el_ejemplo_del_contrato():
    c = cliente(Respuesta(200, ejemplo("parametros", "consultar_ajustes_version")))
    datos = servicios.ajustes_version(c, 31)
    assert c.http.llamadas[0]["ruta"] == "versions/31/parameters"
    assert datos["editable"] is True and datos["ajustes"]["r0"]["valor"] == 3.2
    assert datos["catalogo"]["r0"]["valor"] == 2.87 and datos["efectivos"]["r0"]["valor"] == 3.2


def test_ajustar_manda_el_cuerpo_del_contrato_y_none_quita_el_ajuste():
    c = cliente(Respuesta(200, ejemplo("parametros", "ajustar_parametros_version")),
                Respuesta(200, ejemplo("parametros", "ajustar_parametros_version")))
    pedido = {"r0": {"valor": 3.2, "fuente": None, "supuesto": True}}
    servicios.ajustar_version(c, 31, pedido)
    llamada = c.http.llamadas[0]
    assert (llamada["metodo"], llamada["ruta"]) == ("PUT", "versions/31/parameters")
    assert xmlio.leer(llamada["cuerpo"])["parametros"]["r0"]["valor"] == 3.2
    servicios.ajustar_version(c, 31, {"r0": None})
    assert xmlio.leer(c.http.llamadas[1]["cuerpo"])["parametros"]["r0"] is None


def test_un_rechazo_del_servidor_se_explica():
    c = cliente(problema(422, "DATOS_INVALIDOS", "El parámetro r0 requiere fuente o marcar supuesto."))
    with pytest.raises(api.ErrorServicio) as error:
        servicios.ajustar_version(c, 31, {"r0": {"valor": 3.2, "fuente": None, "supuesto": False}})
    assert error.value.status == 422 and "fuente" in str(error.value)


@pytest.fixture
def qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_las_tasas_se_capturan_en_porcentaje_y_se_mandan_de_0_a_1(qt):
    from frontend_desktop.app.ui.ajustes import ajuste_de, texto_valor
    tasa = {"porcentaje": True}
    assert texto_valor(0.004, tasa) == "0.4 %" and texto_valor(2.87, {}) == "2.87"
    assert texto_valor(None, tasa) is None
    cuerpo = ajuste_de(tasa, 0.4, " Estudio propio ", False, (0.2, 0.6, "IC95"))
    assert cuerpo["valor"] == pytest.approx(0.004) and cuerpo["fuente"] == "Estudio propio"
    assert cuerpo["intervalo"] == {"min": pytest.approx(0.002), "max": pytest.approx(0.006), "tipo": "IC95"}
    assert ajuste_de({}, 3.2, "", True, None) == {"valor": 3.2, "fuente": None, "supuesto": True}


class ClienteAjustes(api.Cliente):
    """Responde con los ejemplos del contrato y guarda lo que se le manda."""

    def __init__(self, editable=True):
        super().__init__("http://directorio")
        self.access, self.editable, self.enviados = "token", editable, []

    def enviar(self, servicio, metodo, ruta, cuerpo=None, params=None, publico=False):
        assert (servicio, ruta) == ("parametros", "/api/v1/versions/31/parameters")
        self.enviados.append((metodo, None if cuerpo is None else xmlio.leer(cuerpo)))
        datos = xmlio.leer(ejemplo("parametros", "consultar_ajustes_version"))
        datos["editable"] = self.editable
        return Respuesta(200, xmlio.escribir(datos, "ajustes_version"))


def abrir(qt, cliente, editable=True):
    from PySide6.QtCore import QThreadPool
    from frontend_desktop.app.ui.ajustes import DialogoAjustes

    class Ventana:
        pass
    Ventana.cliente = cliente
    Ventana.mostrar_error = lambda self, exc: pytest.fail(str(exc))
    dialogo = DialogoAjustes(None, Ventana(), 31, "COVID-19", editable)
    for _ in range(5):
        QThreadPool.globalInstance().waitForDone(5000)
        qt.processEvents()
    return dialogo, QThreadPool


def test_el_dialogo_muestra_catalogo_y_ajuste_y_aplica_uno_nuevo(qt):
    cliente = ClienteAjustes()
    dialogo, pool = abrir(qt, cliente)
    t = dialogo.tabla
    assert t.item(0, 2).text() == "2.87" and t.item(0, 3).text() == "3.2" and t.item(0, 6).text() == "Ajustado"
    assert t.item(1, 6).text() == "Con fuente"
    dialogo.tabla.selectRow(1)
    assert dialogo.aplicar.isEnabled() and not dialogo.quitar.isEnabled()
    dialogo.valor.setValue(4.0)
    dialogo.fuente.setText("Estudio propio")
    dialogo.supuesto.setChecked(False)
    dialogo.aplicar.click()
    for _ in range(5):
        pool.globalInstance().waitForDone(5000)
        qt.processEvents()
    metodo, cuerpo = cliente.enviados[-1]
    assert metodo == "PUT"
    assert cuerpo["parametros"]["incubacion_dias"]["valor"] == 4.0
    assert cuerpo["parametros"]["incubacion_dias"]["fuente"] == "Estudio propio"


def test_volver_al_catalogo_manda_null_solo_si_hay_ajuste(qt):
    cliente = ClienteAjustes()
    dialogo, pool = abrir(qt, cliente)
    dialogo.tabla.selectRow(0)
    assert dialogo.quitar.isEnabled()
    dialogo.quitar.click()
    for _ in range(5):
        pool.globalInstance().waitForDone(5000)
        qt.processEvents()
    assert cliente.enviados[-1][1]["parametros"]["r0"] is None


@pytest.mark.parametrize("editable_servidor,puede", [(False, True), (True, False)])
def test_una_version_enviada_o_ajena_solo_se_consulta(qt, editable_servidor, puede):
    dialogo, _ = abrir(qt, ClienteAjustes(editable_servidor), puede)
    dialogo.tabla.selectRow(0)
    assert not dialogo.aplicar.isEnabled() and not dialogo.valor.isEnabled()
    assert "ya no es editable" in dialogo.nota.text()
