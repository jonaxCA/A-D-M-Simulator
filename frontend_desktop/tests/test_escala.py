from frontend_desktop.app import config, servicios, xmlio
from frontend_desktop.app.ui.simulaciones import texto_escala


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
