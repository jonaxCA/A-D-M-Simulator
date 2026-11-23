"""Bloque A: versiones e intervalos de los parámetros (D58) y firma de la versión aprobada (D55)."""
import os

import pytest

from frontend_desktop.app import api, servicios, xmlio
from frontend_desktop.tests.test_api import Respuesta
from frontend_desktop.tests.test_mfa_reportes_datos import HTTP, ejemplo

DIRECTORIO = xmlio.escribir({"servicios": [{"nombre": n, "url": "http://%s" % n}
                                           for n in ("parametros", "aprobacion")]}, "directorio")


class HTTPServicios(HTTP):
    def get(self, url, **_):
        return Respuesta(200, DIRECTORIO)


def cliente(*respuestas):
    c = api.Cliente("http://directorio", HTTPServicios(*respuestas))
    c.access, c.refresh = "acceso", "renovacion"
    return c


def test_versiones_de_los_parametros_del_contrato():
    c = cliente(Respuesta(200, ejemplo("parametros", "listar_versiones_parametros")))
    versiones = servicios.versiones_parametros(c, 1)
    assert c.http.llamadas[0]["ruta"] == "diseases/1/parameters/versions"
    assert [v["version"] for v in versiones] == [2, 1]
    assert "042" in versiones[1]["reason"]


def test_firma_de_la_version_del_contrato():
    c = cliente(Respuesta(200, ejemplo("aprobacion", "firma_version")))
    firma = servicios.firma_version(c, 11)
    assert c.http.llamadas[0]["ruta"] == "versions/11/signature"
    assert firma["firmada"] is True and firma["integra"] is True
    assert firma["corridas"] == {"coinciden": 2, "distintas": 0, "sin_huella": 1}


@pytest.fixture
def qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_texto_de_la_firma(qt):
    from frontend_desktop.app.ui.escenarios import texto_firma
    firma = xmlio.leer(ejemplo("aprobacion", "firma_version"))
    texto = texto_firma(firma)
    assert "9c56cc51b374c3ba" in texto and "Elena Epidemióloga" in texto
    assert "sigue siendo la que se firmó" in texto
    assert "firmado: 2; con otra entrada: 0; sin huella: 1" in texto
    assert "ATENCIÓN" in texto_firma(dict(firma, integra=False, corridas={"coinciden": 0, "distintas": 3,
                                                                          "sin_huella": 0}))
    assert "no se puede verificar" in texto_firma(dict(firma, firmada=False, huella=None))


def test_el_intervalo_se_muestra_con_su_tipo(qt):
    from frontend_desktop.app.ui.formularios import texto_intervalo
    assert texto_intervalo({"min": 4.5, "max": 5.8, "tipo": "IC95"}) == "4.5 a 5.8 (IC95)"
    assert texto_intervalo(None) is None and texto_intervalo({"min": None, "max": 2}) is None


def test_el_dialogo_lista_las_versiones_de_los_parametros(qt, monkeypatch):
    from PySide6.QtWidgets import QDialog, QTableWidget
    from frontend_desktop.app.ui.formularios import mostrar_parametros
    vistas = []

    def inspeccionar(dialogo):
        tablas = dialogo.findChildren(QTableWidget)
        vistas.append([(t.item(0, 0).text(), t.rowCount()) for t in tablas])

    monkeypatch.setattr(QDialog, "exec", inspeccionar)
    datos = xmlio.leer(ejemplo("parametros", "estado_de_par_metros_epidemiol_gicos"))
    versiones = xmlio.leer(ejemplo("parametros", "listar_versiones_parametros"))["versiones"]
    mostrar_parametros(None, "COVID-19", datos, versiones)
    assert vistas == [[("R₀ — número reproductivo básico", 3), ("2", 2)]]
