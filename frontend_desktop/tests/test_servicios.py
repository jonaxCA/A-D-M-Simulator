from frontend_desktop.app import api, servicios

SERIE = [{"dia": 0, "casos_activos": 10}]


class ClienteFalso:
    def __init__(self, pareto):
        self.respuesta_pareto = pareto
        self.pedidas = []

    def pedir(self, servicio, metodo, ruta, datos=None, raiz=None, params=None, publico=False):
        self.pedidas.append((servicio, params))
        if servicio == "corridas":
            vid = params["scenario_version_id"]
            return {"corridas": [{"id": vid * 10 + s, "seed": s, "scenario_name": "E%s" % vid,
                                  "version_number": 1} for s in (1, 2, 3) if (vid, s) != (2, 3)]}
        if servicio == "comparacion":
            ids = [int(x) for x in params["runs"].split(",")]
            return {"aviso": "No es predicción.", "corridas": [
                {"id": i, "serie": SERIE, "fallecimientos": i, "pico_casos_activos": 5, "dia_pico": 1,
                 "tasa_ataque": 0.1} for i in ids]}
        if isinstance(self.respuesta_pareto, Exception):
            raise self.respuesta_pareto
        return self.respuesta_pareto


def test_compara_solo_semillas_comunes():
    c = ClienteFalso({"filas": [{"id": i, "costo": 0 if i < 20 else 9} for i in (11, 12, 21, 22)]})
    datos = servicios.cargar_comparacion(c, [1, 2], "fallecimientos")
    assert datos["semillas"] == [1, 2]
    assert [e["corridas"] for e in datos["escenarios"]] == [[11, 12], [21, 22]]
    assert datos["escenarios"][1]["dominado_por"] == ["E1 · v1"]


def test_sin_costos_compara_sin_frontera():
    texto = ("SIM-00001 - A: Falta el costo unitario de 'CIERRE_ESCUELAS' (por_habitante_dia). "
             "SIM-00002 - A: Falta el costo unitario de 'CIERRE_ESCUELAS' (por_habitante_dia).")
    c = ClienteFalso(api.ErrorServicio(texto, 422, "DATOS_INVALIDOS"))
    datos = servicios.cargar_comparacion(c, [1, 2], "fallecimientos")
    assert datos["avisos"] == ["Falta el costo unitario de 'CIERRE_ESCUELAS' (por_habitante_dia)."]
    assert all(e["costo"] is None and e["dominado_por"] is None for e in datos["escenarios"])
    assert datos["aviso"] == "No es predicción."
