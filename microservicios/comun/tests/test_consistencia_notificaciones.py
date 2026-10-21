"""Lo que mandan aprobacion y simulador a notificaciones lo acepta la app real.

Las dos llaman a la ruta interna POST /api/v1/notifications con un token de
servicio. Aquí la llamada llega a la app de notificaciones (con la base
simulada), de modo que un campo renombrado, un tipo fuera del CHECK o el token
equivocado rompen esta prueba.
"""
import pytest
import requests

from backend_web import notificaciones, queries
from microservicios.aprobacion import rutas as rutas_aprobacion
from microservicios.simulador import trabajador


class Respuesta(requests.Response):
    def __init__(self, flask):
        super().__init__()
        self.status_code = flask.status_code
        self._content = flask.data


@pytest.fixture
def guardadas(crear_cliente, monkeypatch):
    destino = crear_cliente("notificaciones")
    filas = []

    def crear_notificacion(datos, *, contexto):
        errores = notificaciones.valida_notificacion(datos)
        if errores:
            return None, " ".join(errores)
        filas.append((datos, contexto.user_agent))
        return len(filas), None

    def llamar(servicio, metodo, ruta, formato="json", cuerpo=None, token=None, **_):
        assert servicio == "notificaciones"
        return Respuesta(destino.open(ruta + "?format=json", method=metodo, json=cuerpo,
                                      headers={"Authorization": "Bearer %s" % token}))

    monkeypatch.setattr(notificaciones, "crear_notificacion", crear_notificacion)
    monkeypatch.setattr(rutas_aprobacion, "llamar", llamar)
    monkeypatch.setattr(trabajador, "llamar", llamar)
    return filas


def test_aviso_de_aprobacion(crear_cliente, guardadas, caplog):
    app = crear_cliente("aprobacion").application
    with app.app_context():
        rutas_aprobacion._notificar_aprobacion({"id": 3, "name": "Brote"},
                                               {"id": 11, "version_number": 2, "created_by": 5})
    assert not caplog.records
    (datos, origen), = guardadas
    assert datos["type"] == "SCENARIO_APPROVED" and datos["user_id"] == 5
    assert origen == "servicio aprobacion"


@pytest.mark.parametrize("final", ["completado", "fallido"])
def test_aviso_del_simulador(crear_cliente, guardadas, monkeypatch, caplog, final):
    monkeypatch.setattr(queries, "get_run", lambda run_id: {
        "id": run_id, "requested_by": 5, "scenario_id": 3, "scenario_version_id": 11,
        "scenario_name": "Brote", "version_number": 2, "error_message": "Error forzado."})
    ajustes = crear_cliente("simulador").application.config
    trabajador.avisar(42, final, ajustes)
    assert not caplog.records
    (datos, origen), = guardadas
    assert datos["type"] == trabajador.AVISOS[final][0] and datos["payload"]["run_id"] == 42
    assert origen == "servicio simulador"
