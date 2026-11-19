import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_desktop.app import api, config, exportar, resumen  # noqa: E402

RUTAS = [
    ("estado-servicios", r"/api/v1/services/health", "estado-servicios/ejemplos/salud_servicios.xml"),
    ("tipos-intervencion", r"/api/v1/intervention-types", "tipos-intervencion/ejemplos/listar_tipos_intervencion.xml"),
    ("escenarios", r"/api/v1/scenarios", "escenarios/ejemplos/listar_escenarios.xml"),
    ("escenarios", r"/api/v1/scenarios/\d+", "escenarios/ejemplos/consultar_escenario.xml"),
    ("escenarios", r"/api/v1/scenarios/\d+/versions", "escenarios/ejemplos/historial_versiones.xml"),
    ("validacion", r"/api/v1/versions/\d+/validation", "validacion/ejemplos/validar_version.xml"),
    ("corridas", r"/api/v1/runs", "corridas/ejemplos/listar_corridas.xml"),
    ("corridas", r"/api/v1/runs/\d+", "corridas/ejemplos/consultar_corrida.xml"),
    ("notificaciones", r"/api/v1/notifications", "notificaciones/ejemplos/listar_notificaciones.xml"),
]


class Respuesta:
    status_code = 200
    headers = {}

    def __init__(self, contenido):
        self.content = contenido


class ClienteDeEjemplos(api.Cliente):
    def __init__(self):
        super().__init__("http://directorio")
        self.access = "token"
        self.usuario = {"id": 7, "username": "alex.cavazos", "full_name": "Alex Cavazos", "roles": ["ANALISTA"]}
        self.pedidas = []

    def enviar(self, servicio, metodo, ruta, cuerpo=None, params=None, publico=False):
        self.pedidas.append((servicio, ruta))
        for nombre, patron, archivo in RUTAS:
            if nombre == servicio and re.fullmatch(patron, ruta):
                return Respuesta((config.CONTRATOS / archivo).read_bytes())
        raise api.ErrorServicio("Sin ejemplo para %s %s" % (servicio, ruta))


def esperar(app):
    for _ in range(5):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()


def datos_comparacion():
    serie = [{"dia": d, "casos_activos": 10 * d} for d in range(5)]
    elegidas = {v: [{"id": v * 10 + s, "seed": s, "scenario_name": n, "version_number": 1} for s in (1, 2)]
                for v, n in ((1, "Base"), (2, "Cierre"))}
    comparadas = [{"id": i, "serie": serie, "fallecimientos": f, "pico_casos_activos": 40, "dia_pico": 4,
                   "tasa_ataque": 0.3} for i, f in ((11, 100), (12, 110), (21, 60), (22, 70))]
    pareto = {"filas": [{"id": i, "costo": c} for i, c in ((11, 0), (12, 0), (21, 5e6), (22, 5e6))],
              "trazabilidad_costos": [{"tipo": "CIERRE_ESCUELAS", "valor": 15, "unidad": "por_habitante_dia",
                                       "fuente": None, "estado": "supuesto"}],
              "modelo_costo": "unitario x poblacion", "aviso": "No es una predicción."}
    return resumen.armar(elegidas, comparadas, pareto, "fallecimientos", "")


def test_la_ventana_carga_con_respuestas_de_ejemplo(tmp_path):
    from frontend_desktop.app.ui.ventana import Ventana
    app = QApplication.instance() or QApplication([])
    errores = []
    Ventana.mostrar_error = lambda self, exc: errores.append(exc)
    cliente = ClienteDeEjemplos()
    ventana = Ventana(cliente)
    esperar(app)
    ventana.ir(1)
    esperar(app)
    assert errores == []

    escenarios = ventana.escenarios
    assert escenarios.lista.count() == 1
    escenarios.abrir(12)
    esperar(app)
    assert errores == []
    assert escenarios.intervenciones.rowCount() == 1
    assert escenarios.versiones.count() == 2
    assert escenarios.form.tipo.count() == 3

    simulaciones = ventana.simulaciones
    assert simulaciones.tabla.rowCount() == 1
    assert simulaciones.pestanas.tabText(3) == "Todas · 2"
    assert "1 ejecutando" in ventana.cola.text()

    comparacion = ventana.comparacion
    comparacion._mostrar(datos_comparacion())
    assert comparacion.tabla.rowCount() == 2
    assert "No es una predicción." in comparacion.aviso.text()
    assert "2 de 2 escenarios están en la frontera" in comparacion.lectura.text()
    imagenes = comparacion._imagenes()
    pdf = tmp_path / "reporte.pdf"
    exportar.guardar_pdf(pdf, comparacion._html(imagenes), imagenes)
    assert pdf.read_bytes().startswith(b"%PDF")
    tabla, curvas = exportar.csv_comparacion(tmp_path / "comparacion.csv", comparacion.datos)
    assert "Cierre · v1" in tabla.read_text(encoding="utf-8-sig") and curvas.exists()
    ventana.reingresando = True
    ventana.close()
