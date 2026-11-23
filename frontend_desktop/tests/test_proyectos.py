"""Bloque A: proyectos de investigación y archivado de escenarios en el escritorio (D54, RF-D12, RF-D19)."""
import os

import pytest

from frontend_desktop.app import api, servicios, xmlio
from frontend_desktop.tests.test_api import Respuesta
from frontend_desktop.tests.test_mfa_reportes_datos import cliente, cuerpo, ejemplo


def leido(nombre):
    return xmlio.leer(ejemplo("escenarios", nombre))


def test_lista_y_detalle_de_proyectos():
    c = cliente(Respuesta(200, ejemplo("escenarios", "listar_proyectos")),
                Respuesta(200, ejemplo("escenarios", "consultar_proyecto")))
    lista = servicios.proyectos(c, "activo")
    assert c.http.llamadas[0]["ruta"] == "projects" and c.http.llamadas[0]["params"] == {"status": "activo"}
    assert [(p["id"], p["motores"], p["n_escenarios"]) for p in lista] == [(4, ["seir-ref", "abm-ref"], 2)]
    detalle = servicios.proyecto(c, 4)
    assert [e["id"] for e in detalle["escenarios"]] == [12, 14]
    assert detalle["escenarios"][0]["version_status"] == "aprobado"


def test_crear_proyecto_manda_el_cuerpo_del_contrato():
    c = cliente(Respuesta(201, ejemplo("escenarios", "crear_proyecto")))
    peticion = leido("crear_proyecto_peticion")
    proyecto = servicios.crear_proyecto(c, peticion)
    llamada = c.http.llamadas[0]
    assert (llamada["metodo"], llamada["ruta"]) == ("POST", "projects")
    assert llamada["cuerpo"].endswith(ejemplo("escenarios", "crear_proyecto_peticion").split(b"?>", 1)[1].strip())
    assert cuerpo(llamada) == peticion
    assert proyecto["status"] == "activo" and proyecto["n_escenarios"] == 0


def test_cambiar_archivar_y_restaurar():
    c = cliente(Respuesta(200, ejemplo("escenarios", "cambiar_proyecto")),
                Respuesta(200, ejemplo("escenarios", "archivar_proyecto")),
                Respuesta(200, ejemplo("escenarios", "restaurar_proyecto")))
    servicios.cambiar_proyecto(c, 4, {"period_end": "2027-04-30"})
    assert c.http.llamadas[0]["metodo"] == "PATCH" and cuerpo(c.http.llamadas[0]) == leido("cambiar_proyecto_peticion")
    assert servicios.archivar_proyecto(c, 4)["status"] == "archivado"
    servicios.archivar_proyecto(c, 4, archivar=False)
    assert [x["ruta"] for x in c.http.llamadas[1:]] == ["projects/4/archive", "projects/4/restore"]


def test_meter_y_sacar_un_escenario_del_proyecto():
    c = cliente(Respuesta(200, ejemplo("escenarios", "mover_a_proyecto")),
                Respuesta(200, xmlio.escribir({"scenario_id": 12, "project_id": None}, "escenario")))
    assert servicios.mover_a_proyecto(c, 12, 4) == {"scenario_id": 12, "project_id": 4}
    meter = c.http.llamadas[0]
    assert (meter["metodo"], meter["ruta"]) == ("PUT", "scenarios/12/project")
    assert cuerpo(meter) == leido("mover_a_proyecto_peticion")
    servicios.mover_a_proyecto(c, 12, None)
    assert b'<project_id nil="true" />' in c.http.llamadas[1]["cuerpo"]


def test_archivar_y_restaurar_un_escenario():
    c = cliente(Respuesta(200, ejemplo("escenarios", "archivar_escenario")),
                Respuesta(200, xmlio.escribir({"id": 12, "status": "borrador"}, "escenario")))
    assert servicios.archivar_escenario(c, 12) == {"id": 12, "status": "archivado"}
    assert servicios.archivar_escenario(c, 12, archivar=False)["status"] == "borrador"
    assert [x["ruta"] for x in c.http.llamadas] == ["scenarios/12/archive", "scenarios/12/restore"]


def test_la_lista_de_escenarios_filtra_por_proyecto_y_archivados():
    c = cliente(Respuesta(200, ejemplo("escenarios", "listar_escenarios")),
                Respuesta(200, ejemplo("escenarios", "listar_escenarios")))
    assert servicios.escenarios(c)[0]["project_id"] == 4
    assert c.http.llamadas[0]["params"] is None
    servicios.escenarios(c, "gripe", proyecto_id=4, archivados=True)
    assert c.http.llamadas[1]["params"] == {"q": "gripe", "project_id": 4, "archived": "true"}


# --- Pantalla -----------------------------------------------------------------------------------

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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
    def __init__(self, usuario_id=7, admin=False):
        self.cliente = api.Cliente("http://directorio")
        self.cliente.usuario = {"id": usuario_id}
        self.admin = admin
        self.errores, self.acciones, self.abiertos = [], [], []

    def es_admin(self):
        return self.admin

    def mostrar_error(self, exc):
        self.errores.append(exc)

    def accion(self, texto):
        self.acciones.append(texto)

    def abrir_escenario(self, escenario_id, version):
        self.abiertos.append(escenario_id)


@pytest.fixture
def servidor(monkeypatch):
    """escenarios de mentira: guarda lo que se le pide y responde con los ejemplos del contrato."""
    pedidos = []
    detalle = leido("consultar_proyecto")
    otros = [{"id": 20, "name": "Otro brote", "version_number": 1, "enfermedad": "Influenza estacional",
              "region": "Monterrey", "project_id": None},
             {"id": 21, "name": "Sarampión", "version_number": 1, "enfermedad": "Sarampión",
              "region": "Monterrey", "project_id": None},
             {"id": 12, "name": "Ya está", "version_number": 2, "enfermedad": "Influenza estacional",
              "region": "Monterrey", "project_id": 4}]
    monkeypatch.setattr(servicios, "enfermedades", lambda c: [{"id": 3, "nombre": "Influenza estacional"},
                                                              {"id": 4, "nombre": "Sarampión"}])
    monkeypatch.setattr(servicios, "regiones", lambda c: [{"id": 5, "nombre": "Monterrey"}])
    monkeypatch.setattr(servicios, "proyectos", lambda c, estado=None: [p for p in leido("listar_proyectos")[
        "proyectos"] if estado in (None, p["status"])])
    monkeypatch.setattr(servicios, "proyecto", lambda c, i: detalle)
    monkeypatch.setattr(servicios, "escenarios", lambda c, *a, **k: otros)

    def registra(nombre, respuesta):
        def fn(c, *args):
            pedidos.append((nombre,) + args)
            return respuesta(*args)
        monkeypatch.setattr(servicios, nombre, fn)

    registra("crear_proyecto", lambda datos: dict(detalle, **datos))
    registra("cambiar_proyecto", lambda i, cambios: dict(detalle, **cambios))
    registra("archivar_proyecto", lambda i, archivar: dict(detalle, status="archivado" if archivar else "activo"))
    registra("mover_a_proyecto", lambda e, p: {"scenario_id": e, "project_id": p})
    registra("archivar_escenario", lambda e, archivar: {"id": e, "status": "archivado" if archivar else "borrador"})
    return pedidos


def abrir_vista(qt, ventana):
    from frontend_desktop.app.ui.proyectos import VistaProyectos
    app, widgets, esperar = qt
    vista = VistaProyectos(ventana)
    widgets.append(vista)
    vista.al_mostrar()
    esperar(app)
    return vista


def test_la_pantalla_lista_abre_y_muestra_sus_escenarios(qt, servidor):
    app, _, esperar = qt
    ventana = Ventana()
    vista = abrir_vista(qt, ventana)
    assert vista.tabla.rowCount() == 1 and vista.tabla.item(0, 6).text() == "Activo"
    assert not vista.marco_escenarios.isVisibleTo(vista), "un proyecto nuevo no tiene escenarios"
    vista.tabla.selectRow(0)
    esperar(app)
    assert vista.nombre.text() == "Influenza en Monterrey, temporada 2026"
    assert vista.enfermedad.currentData() == 3 and vista.region.currentData() == 5
    assert not vista.enfermedad.isEnabled() and not vista.region.isEnabled(), "con escenarios no cambian"
    assert vista.motores["abm-ref"].isChecked() and not vista.motores["abm-gpu"].isChecked()
    assert vista.escenarios.rowCount() == 2 and vista.escenarios.item(0, 2).text() == "Aprobado"
    assert [vista.agregar_combo.itemData(i) for i in range(vista.agregar_combo.count())] == [20]
    vista.escenarios.selectRow(0)
    vista.abrir_escenario()
    assert ventana.abiertos == [12] and not ventana.errores


def test_crear_un_proyecto(qt, servidor):
    app, _, esperar = qt
    vista = abrir_vista(qt, Ventana())
    vista.nombre.setText("ab")
    vista.guardar_proyecto()
    assert "al menos 3" in vista.mensaje.text() and servidor == []
    vista.nombre.setText("Sarampión en Monterrey")
    vista.enfermedad.setCurrentIndex(1)
    vista.motores["abm-ref"].setChecked(True)
    vista.guardar_proyecto()
    esperar(app)
    (nombre, datos), = servidor
    assert nombre == "crear_proyecto"
    assert (datos["name"], datos["disease_id"], datos["region_id"], datos["motores"]) == (
        "Sarampión en Monterrey", 4, 5, ["seir-ref", "abm-ref"])
    assert datos["objective"] is None and datos["period_start"] <= datos["period_end"]


def test_guardar_manda_solo_lo_que_cambio(qt, servidor):
    app, _, esperar = qt
    from PySide6.QtCore import QDate
    vista = abrir_vista(qt, Ventana())
    vista.tabla.selectRow(0)
    esperar(app)
    vista.guardar_proyecto()
    assert "No hay cambios" in vista.mensaje.text() and servidor == []
    vista.fin.setDate(QDate(2027, 4, 30))
    vista.guardar_proyecto()
    esperar(app)
    assert servidor[0] == ("cambiar_proyecto", 4, {"period_end": "2027-04-30"})


def test_meter_sacar_y_archivar_escenarios(qt, servidor, monkeypatch):
    app, _, esperar = qt
    from frontend_desktop.app.ui import proyectos as modulo
    monkeypatch.setattr(modulo.QMessageBox, "question", lambda *a, **k: modulo.QMessageBox.Yes)
    vista = abrir_vista(qt, Ventana())
    vista.tabla.selectRow(0)
    esperar(app)
    vista.agregar_escenario()
    esperar(app)
    vista.escenarios.selectRow(1)
    assert vista.b_archivar_esc.text() == "Archivar escenario"
    vista.sacar_escenario()
    esperar(app)
    vista.escenarios.selectRow(0)
    vista.archivar_escenario()
    esperar(app)
    vista.archivar_proyecto()
    esperar(app)
    assert servidor == [("mover_a_proyecto", 20, 4), ("mover_a_proyecto", 14, None),
                        ("archivar_escenario", 12, True), ("archivar_proyecto", 4, True)]
    assert len(vista.v.acciones) == 4 and not vista.v.errores


def test_quien_no_es_dueno_ni_administrador_no_edita(qt, servidor):
    app, _, esperar = qt
    vista = abrir_vista(qt, Ventana(usuario_id=99))
    vista.tabla.selectRow(0)
    esperar(app)
    assert not vista.guardar.isEnabled() and not vista.archivar.isEnabled() and not vista.nombre.isEnabled()
    admin = abrir_vista(qt, Ventana(usuario_id=99, admin=True))
    admin.tabla.selectRow(0)
    esperar(app)
    assert admin.guardar.isEnabled() and admin.archivar.isEnabled()


def test_proyecto_archivado_solo_se_restaura(qt, servidor, monkeypatch):
    app, _, esperar = qt
    archivado = dict(leido("consultar_proyecto"), status="archivado")
    monkeypatch.setattr(servicios, "proyecto", lambda c, i: archivado)
    vista = abrir_vista(qt, Ventana())
    vista.tabla.selectRow(0)
    esperar(app)
    assert vista.archivar.text() == "Restaurar proyecto" and vista.archivar.isEnabled()
    assert not vista.guardar.isEnabled() and not vista.b_agregar.isEnabled()
    vista.archivar_proyecto()
    esperar(app)
    assert servidor[-1] == ("archivar_proyecto", 4, False)


def test_el_rechazo_del_servidor_se_explica_en_la_pantalla(qt, servidor, monkeypatch):
    app, _, esperar = qt

    def rechaza(c, e, p):
        raise api.ErrorServicio("El escenario es de otra enfermedad o región.", 409, "CONFLICTO")

    monkeypatch.setattr(servicios, "mover_a_proyecto", rechaza)
    vista = abrir_vista(qt, Ventana())
    vista.tabla.selectRow(0)
    esperar(app)
    vista.agregar_escenario()
    esperar(app)
    assert "otra enfermedad" in vista.mensaje.text() and not vista.v.errores
