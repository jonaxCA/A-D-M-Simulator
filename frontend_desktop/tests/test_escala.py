import pytest

# texto_escala vive en una vista de Qt: sin PySide6 se salta, como test_humo.py.
pytest.importorskip("PySide6")

from frontend_desktop.app import config, servicios, xmlio  # noqa: E402
from frontend_desktop.app.ui.simulaciones import texto_escala  # noqa: E402


def test_escala_con_ejemplo_real():
    archivo = config.CONTRATOS / "resultados/ejemplos/consultar_resultado.xml"
    datos = xmlio.leer(archivo.read_bytes())
    texto = texto_escala(datos["escala"])

    assert "200,000" in texto
    assert "1,142,994" in texto
    assert "1 agente representa" in texto


def test_escala_sin_datos():
    assert "no devolvió" in texto_escala(None)
    assert "No hay datos suficientes" in texto_escala({
        "agentes": None, "habitantes": None, "factor": None
    })


def test_servicio_consulta_resultados_xml():
    class ClienteFalso:
        def pedir(self, servicio, metodo, ruta):
            self.llamada = (servicio, metodo, ruta)
            return {"escala": {
                "agentes": 100,
                "habitantes": 500,
                "factor": 5,
            }}

    cliente = ClienteFalso()
    datos = servicios.escala_corrida(cliente, 42)

    assert cliente.llamada == (
        "resultados", "GET", "/api/v1/runs/42/results"
    )
    assert datos["escala"]["factor"] == 5
    assert datos["run_id"] == 42


def test_escala_muestra_lineas_separadas():
    texto = texto_escala({
        "agentes": 10,
        "habitantes": 50,
        "factor": 5,
        "fuente": "Censo",
        "avisos": ["Valor de demostracion"],
    })
    assert texto.splitlines() == [
        "Agentes simulados: 10",
        "Habitantes representados: 50",
        "1 agente representa aproximadamente 5.00 habitantes.",
        "Fuente: Censo",
        "Aviso: Valor de demostracion",
    ]
