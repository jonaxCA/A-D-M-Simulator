import os

import pytest

from frontend_desktop.app import api, servicios, xmlio
from frontend_desktop.tests.test_api import Respuesta, problema
from frontend_desktop.tests.test_mfa_reportes_datos import HTTP, cuerpo, ejemplo

DIRECTORIO = xmlio.escribir({"servicios": [{"nombre": n, "url": "http://%s" % n} for n in (
    "calibracion", "escenarios", "intervenciones", "parametros", "importacion")]}, "directorio")


class HTTPCalibracion(HTTP):
    def get(self, url, **_):
        return Respuesta(200, DIRECTORIO)


def cliente(*respuestas):
    c = api.Cliente("http://directorio", HTTPCalibracion(*respuestas))
    c.access, c.refresh = "acceso", "renovacion"
    return c


def leido(nombre):
    return xmlio.leer(ejemplo("calibracion", nombre))


def test_lista_y_detalle():
    c = cliente(Respuesta(200, ejemplo("calibracion", "listar_calibraciones")),
                Respuesta(200, ejemplo("calibracion", "consultar_calibracion")))
    lista = servicios.calibraciones(c, "completado", 1)
    assert c.http.llamadas[0]["params"] == {"status": "completado", "dataset": 1}
    assert [(k["id"], k["status"]) for k in lista] == [(4, "ejecutando"), (3, "completado")]
    k = servicios.calibracion(c, 3)
    assert [p["nombre"] for p in k["estimados"]] == ["r0", "rho", "phi"]
    assert k["metricas"]["validacion"]["r2"] < 0


def test_lanzar_manda_el_cuerpo_del_contrato():
    c = cliente(Respuesta(202, ejemplo("calibracion", "lanzar_calibracion")))
    k = servicios.lanzar_calibracion(c, 1, 5000, 3, 0.01, 1)
    llamada = c.http.llamadas[0]
    assert (llamada["metodo"], llamada["ruta"]) == ("POST", "calibrations")
    assert cuerpo(llamada) == leido("lanzar_calibracion.peticion")
    assert k["status"] == "encolado"


def test_cancelar_ajuste_evaluar_y_estado():
    c = cliente(Respuesta(200, ejemplo("calibracion", "cancelar_calibracion")),
                Respuesta(200, ejemplo("calibracion", "ajuste_calibracion")),
                Respuesta(200, ejemplo("calibracion", "evaluar_parametros")),
                Respuesta(200, ejemplo("calibracion", "estado_calibracion")))
    assert servicios.cancelar_calibracion(c, 4)["status"] == "cancelado"
    ajuste = servicios.ajuste_calibracion(c, 3)
    assert {s["ventana"] for s in ajuste["semanas"]} == {"calibracion", "validacion"}
    evaluacion = servicios.evaluar_parametros(c, 1, 2.59, 0.3, 0.37)
    assert len(evaluacion["semanas"]) == 22 and evaluacion["aviso"]
    estado = servicios.estado_calibracion(c, 1, 1)
    assert estado["modelos"][0]["estado"] == "sin_calibrar"
    rutas = [(x["metodo"], x["ruta"], x["params"]) for x in c.http.llamadas]
    assert rutas == [("POST", "calibrations/4/cancel", None), ("GET", "calibrations/3/fit", None),
                     ("GET", "calibrations/evaluate", {"dataset": 1, "r0": 2.59, "rho": 0.3, "phi": 0.37}),
                     ("GET", "calibrations/state", {"disease": 1, "region": 1})]


def test_borrador_calibrado_crea_escenario_intervenciones_y_r0():
    c = cliente(Respuesta(200, ejemplo("calibracion", "escenario_calibrado")),
                Respuesta(201, ejemplo("escenarios", "crear_escenario")),
                Respuesta(200, ejemplo("escenarios", "consultar_escenario")),
                *[Respuesta(201, ejemplo("intervenciones", "agregar_intervencion")) for _ in range(3)],
                Respuesta(200, ejemplo("parametros", "ajustar_parametros_version")))
    creado = servicios.crear_borrador_calibrado(c, 3)
    pedidas = [(x["metodo"], x["ruta"]) for x in c.http.llamadas]
    assert pedidas == [("GET", "calibrations/3/scenario"), ("POST", "scenarios"), ("GET", "scenarios/13"),
                       ("POST", "versions/31/interventions"), ("POST", "versions/31/interventions"),
                       ("POST", "versions/31/interventions"), ("PUT", "versions/31/parameters")]
    escenario = cuerpo(c.http.llamadas[1])
    assert escenario["stratify"] is True and "population_size" not in escenario
    assert "CIERRE_ESCUELAS: Acuerdo SEP" in escenario["notes"]
    assert set(cuerpo(c.http.llamadas[3])) == {"code", "start_day", "end_day", "coverage", "compliance", "params"}
    assert cuerpo(c.http.llamadas[6])["parametros"]["r0"]["supuesto"] is False
    assert creado["intervenciones"] == 3 and creado["escenario_id"] == 13


@pytest.fixture
def qt():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from frontend_desktop.tests.test_humo import esperar
    app = QApplication.instance() or QApplication([])
    widgets = []
    yield app, widgets, esperar
    esperar(app)
    for widget in widgets:
        widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class Ventana:
    def __init__(self):
        self.cliente = api.Cliente("http://directorio")
        self.errores, self.acciones, self.abiertos = [], [], []

    def mostrar_error(self, exc):
        self.errores.append(exc)

    def accion(self, texto):
        self.acciones.append(texto)

    def abrir_escenario(self, escenario_id, version):
        self.abiertos.append((escenario_id, version))


@pytest.fixture
def servidor(monkeypatch):
    listado = leido("listar_calibraciones")["calibraciones"]
    monkeypatch.setattr(servicios, "calibraciones", lambda c, *a: listado)
    monkeypatch.setattr(servicios, "conjuntos", lambda c: [{"id": 1, "code": "COVID19_NL_2020_SINTOMAS", "version": 1}])
    monkeypatch.setattr(servicios, "calibracion", lambda c, i: dict(
        leido("consultar_calibracion"), id=i, status=next(k["status"] for k in listado if k["id"] == i)))
    monkeypatch.setattr(servicios, "ajuste_calibracion", lambda c, i: leido("ajuste_calibracion"))
    return listado


def vista(qt):
    from frontend_desktop.app.ui.calibracion import VistaCalibracion
    app, widgets, esperar = qt
    v = VistaCalibracion(Ventana())
    widgets.append(v)
    v.al_mostrar()
    esperar(app)
    return app, v, esperar


def test_la_pantalla_lista_y_sondea_solo_mientras_hay_una_en_curso(qt, servidor):
    app, v, esperar = vista(qt)
    assert v.tabla.rowCount() == 2 and v.conjunto.count() == 1
    assert v.reloj.isActive()
    assert not v.b_escenario.isEnabled() and not v.b_cancelar.isEnabled()
    servidor[0]["status"] = "completado"
    v.cargar()
    esperar(app)
    assert not v.reloj.isActive() and not v.v.errores


def test_la_completada_muestra_ajuste_y_deja_crear_el_borrador(qt, servidor):
    app, v, esperar = vista(qt)
    v.tabla.selectRow(1)
    esperar(app)
    assert v.estimados.rowCount() == 3 and v.metricas.rowCount() == 2
    assert v.metricas.item(1, 3).text() == "-25.92" and v.metricas.item(1, 4).text() == "71%"
    assert "al menos 80%" in v.pie.text() and "incertidumbre de los parámetros" in v.pie.text()
    series = v.grafica.chart().series()
    assert any(s.name() == "Observado" and s.count() == 22 for s in series)
    assert any(s.name() == "Inicio de la validación" for s in series)
    assert v.b_escenario.isEnabled() and not v.b_cancelar.isEnabled()


def test_la_en_curso_se_puede_cancelar_y_no_crea_escenario(qt, servidor):
    app, v, esperar = vista(qt)
    v.tabla.selectRow(0)
    esperar(app)
    assert v.b_cancelar.isEnabled() and not v.b_escenario.isEnabled()


def test_un_rechazo_del_servidor_se_explica_sin_ventana_de_error(qt, servidor, monkeypatch):
    def rechazar(*a):
        raise api.ErrorServicio("Demasiadas calibraciones en curso", 429)

    monkeypatch.setattr(servicios, "lanzar_calibracion", rechazar)
    app, v, esperar = vista(qt)
    v.b_lanzar.click()
    esperar(app)
    assert "Demasiadas calibraciones" in v.mensaje.text() and not v.v.errores
    assert v.b_lanzar.isEnabled()


def test_un_403_se_entrega_a_la_ventana(qt, servidor, monkeypatch):
    def prohibir(*a):
        raise api.ErrorServicio("No tienes permiso", 403)

    monkeypatch.setattr(servicios, "lanzar_calibracion", prohibir)
    app, v, esperar = vista(qt)
    v.b_lanzar.click()
    esperar(app)
    assert len(v.v.errores) == 1 and v.b_lanzar.isEnabled()


def test_crear_escenario_abre_el_borrador(qt, servidor, monkeypatch):
    monkeypatch.setattr(servicios, "crear_borrador_calibrado",
                        lambda c, i: {"escenario_id": 13, "version": {"id": 31, "version_number": 1},
                                      "intervenciones": 3})
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *a: None)
    app, v, esperar = vista(qt)
    v.tabla.selectRow(1)
    esperar(app)
    v.b_escenario.click()
    esperar(app)
    assert v.v.abiertos == [(13, 1)] and v.v.acciones[-1].startswith("creó el escenario 13")
