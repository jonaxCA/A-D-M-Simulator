import pytest

from frontend_desktop.app import api
from frontend_desktop.app.ui import ventana


@pytest.fixture
def capturar(monkeypatch):
    ventanas = []
    registros = []

    class CajaFalsa:
        Warning = 1

        def __init__(self, icono, titulo, mensaje, parent=None):
            self.mensaje = mensaje
            self.detalle = ""
            ventanas.append(self)

        def setDetailedText(self, texto):
            self.detalle = texto

        def exec(self):
            return 0

    monkeypatch.setattr(ventana, "QMessageBox", CajaFalsa)
    monkeypatch.setattr(
        ventana.bitacora, "error", lambda texto: registros.append(texto)
    )
    return ventanas, registros


def test_403_no_muestra_datos_internos(capturar):
    cajas, registros = capturar
    error = api.ErrorServicio(
        "Traceback: consulta SQL interna", 403,
        errores=[{"ruta": "SQL", "mensaje": "dato privado"}]
    )
    ventana.Ventana.mostrar_error(object(), error)
    assert cajas[0].mensaje == "No tienes permiso para esta operación."
    assert cajas[0].detalle == ""
    assert "Traceback" not in str(registros)


def test_503_no_muestra_datos_internos(capturar):
    cajas, registros = capturar
    error = api.ErrorServicio(
        "Traceback: servidor caido", 503
    )
    ventana.Ventana.mostrar_error(object(), error)
    assert cajas[0].mensaje == (
        "El servicio no está disponible. Intenta más tarde."
    )
    assert "Traceback" not in str(registros)


def test_sin_conexion_muestra_error_claro(capturar):
    cajas, _ = capturar
    error = api.ErrorServicio("No se pudo conectar con corridas.")
    ventana.Ventana.mostrar_error(object(), error)
    assert cajas[0].mensaje == "No se pudo conectar con corridas."


def test_sesion_vencida_pide_reingreso(capturar):
    cajas, _ = capturar

    class VentanaFalsa:
        def reingresar(self, motivo):
            self.motivo = motivo

    objeto = VentanaFalsa()
    error = api.SesionCerrada(
        "La sesión terminó. Vuelve a iniciar sesión.", 401
    )
    ventana.Ventana.mostrar_error(objeto, error)
    assert "Vuelve a iniciar sesión" in objeto.motivo
    assert cajas == []


def test_validacion_conserva_detalles(capturar):
    cajas, _ = capturar
    error = api.ErrorServicio(
        "Datos inválidos", 422,
        errores=[{
            "ruta": "cobertura",
            "mensaje": "debe estar entre 0 y 1"
        }]
    )
    ventana.Ventana.mostrar_error(object(), error)
    assert cajas[0].mensaje == "Datos inválidos"
    assert "cobertura" in cajas[0].detalle
