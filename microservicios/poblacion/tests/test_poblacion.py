from xml.etree import ElementTree as ET

import pytest

from backend_web import queries

MONTERREY = {"id": 39, "code": "19039", "name": "Monterrey", "level": "municipio",
             "parent_region_id": 1, "population": 1142994, "population_60plus": 158771}
GRUPOS = {"0-19": 339877, "20-39": 368040, "40-59": 270203, "60-79": 135964, "80+": 22807}
CONFLICTO_POBLACION = ("Otra persona corrigió este municipio mientras editabas el "
                       "formulario. Recarga la página y vuelve a intentarlo.")
CONFLICTO_BANDAS = "Otra persona corrigió las bandas mientras editabas. Recarga la página e intenta de nuevo."


@pytest.fixture
def llamadas(monkeypatch):
    registro = {"poblacion": [], "grupos": [], "respuesta": (True, None, None)}

    def actualiza_poblacion(region_id, population, motivo, esperado, *, contexto):
        registro["poblacion"].append((region_id, population, motivo, esperado, contexto.user_id))
        return registro["respuesta"]

    def actualiza_grupos(region_id, grupos, esperados, motivo, *, contexto):
        registro["grupos"].append((region_id, grupos, esperados, motivo, contexto.user_id))
        return registro["respuesta"]

    monkeypatch.setattr(queries, "get_region_municipio",
                        lambda i: dict(MONTERREY) if i == 39 else None)
    monkeypatch.setattr(queries, "get_grupos_edad_municipio",
                        lambda i: {"grupos": dict(GRUPOS), "edad_no_especificada": 6103} if i == 39 else None)
    monkeypatch.setattr(queries, "actualiza_poblacion_municipio", actualiza_poblacion)
    monkeypatch.setattr(queries, "actualiza_grupos_edad_municipio", actualiza_grupos)
    return registro


@pytest.fixture
def cliente(crear_cliente, llamadas):
    return crear_cliente("poblacion")


@pytest.fixture
def admin(token):
    return token(roles=("ADMINISTRADOR",))


def correccion(**cambios):
    cuerpo = {"population": 1150000, "expected_population": 1142994,
              "reason": "Conteo municipal 2026"}
    cuerpo.update(cambios)
    return cuerpo


def correccion_grupos(**cambios):
    grupos = dict(GRUPOS, **{"0-19": 339870, "20-39": 368047})
    cuerpo = {"groups": grupos, "expected_groups": dict(GRUPOS, edad_no_especificada=6103),
              "reason": "Reclasificación de registros 2026"}
    cuerpo.update(cambios)
    return cuerpo


def test_poblacion_xml_por_omision(cliente):
    r = cliente.get("/api/v1/regions/39/population")
    assert r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "poblacion" and raiz.findtext("population") == "1142994"


def test_poblacion_json_con_format_y_con_accept(cliente):
    datos = cliente.get("/api/v1/regions/39/population?format=json").get_json()
    assert datos == {"region_id": 39, "population": 1142994, "population_60plus": 158771}
    r = cliente.get("/api/v1/regions/39/population", headers={"Accept": "application/json"})
    assert r.content_type.startswith("application/json")


def test_format_invalido_es_400(cliente):
    assert cliente.get("/api/v1/regions/39/population?format=txt").status_code == 400


@pytest.mark.parametrize("ruta", ["/api/v1/regions/1/population", "/api/v1/regions/1/age-groups"])
def test_municipio_inexistente_es_404(cliente, ruta):
    r = cliente.get(ruta + "?format=json")
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"


def test_grupos_en_json(cliente):
    datos = cliente.get("/api/v1/regions/39/age-groups?format=json").get_json()
    assert datos["grupos"] == GRUPOS and datos["edad_no_especificada"] == 6103


def test_grupos_en_xml_valido(cliente):
    respuesta = cliente.get("/api/v1/regions/39/age-groups")
    assert respuesta.status_code == 200
    raiz = ET.fromstring(respuesta.data)
    assert raiz.find(".//entrada[@clave='0-19']") is not None
    assert raiz.find(".//entrada[@clave='80+']") is not None


@pytest.mark.parametrize("ruta,cuerpo", [
    ("/api/v1/regions/39/population", correccion()),
    ("/api/v1/regions/39/age-groups", correccion_grupos()),
])
def test_escritura_sin_token_401_y_solo_administrador(cliente, token, ruta, cuerpo):
    assert cliente.put(ruta + "?format=json", json=cuerpo).status_code == 401
    for rol in ("ANALISTA", "EPIDEMIOLOGO"):
        r = cliente.put(ruta + "?format=json", json=cuerpo, headers=token(roles=(rol,)))
        assert r.status_code == 403


def test_corregir_poblacion_pasa_el_contexto_que_audita(cliente, admin, llamadas):
    llamadas["respuesta"] = (True, None, {"municipio": "Monterrey", "poblacion_antes": 1142994,
                                          "poblacion_despues": 1150000, "estado_actualizado": True})
    r = cliente.put("/api/v1/regions/39/population?format=json", headers=admin, json=correccion())
    assert r.status_code == 200 and r.get_json()["poblacion_despues"] == 1150000
    assert llamadas["poblacion"] == [(39, 1150000, "Conteo municipal 2026", 1142994, 7)]


def test_corregir_poblacion_en_xml(cliente, admin, llamadas):
    xml = (b"<solicitud><population>1150000</population><expected_population>1142994"
           b"</expected_population><reason>Conteo municipal 2026</reason></solicitud>")
    r = cliente.put("/api/v1/regions/39/population?format=json",
                    headers={**admin, "Content-Type": "application/xml"}, data=xml)
    assert r.status_code == 200
    assert llamadas["poblacion"][0][1:4] == (1150000, "Conteo municipal 2026", 1142994)


def test_poblacion_cambiada_por_otra_persona_es_409(cliente, admin, llamadas):
    llamadas["respuesta"] = (False, CONFLICTO_POBLACION, None)
    r = cliente.put("/api/v1/regions/39/population?format=json", headers=admin, json=correccion())
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"


@pytest.mark.parametrize("cuerpo", [
    correccion(population=-5),
    correccion(population=100),
    correccion(reason="   "),
    correccion(reason=12),
    correccion(expected_population=0),
    {"population": 1150000, "reason": "Sin valor esperado"},
    correccion(population_60plus=1),
])
def test_correccion_de_poblacion_invalida_es_422(cliente, admin, llamadas, cuerpo):
    r = cliente.put("/api/v1/regions/39/population?format=json", headers=admin, json=cuerpo)
    assert r.status_code == 422
    assert llamadas["poblacion"] == []


def test_corregir_grupos_pasa_el_contexto(cliente, admin, llamadas):
    llamadas["respuesta"] = (True, None, {"municipio": "Monterrey", "population_60plus": 158771,
                                          "estado_actualizado": True})
    r = cliente.put("/api/v1/regions/39/age-groups?format=json", headers=admin, json=correccion_grupos())
    assert r.status_code == 200
    region_id, grupos, _, motivo, usuario = llamadas["grupos"][0]
    assert (region_id, grupos["0-19"], motivo, usuario) == (39, 339870, "Reclasificación de registros 2026", 7)


def test_corregir_grupos_envia_la_edad_no_especificada_esperada(cliente, admin, llamadas):
    cliente.put("/api/v1/regions/39/age-groups?format=json", headers=admin, json=correccion_grupos())
    assert llamadas["grupos"][0][2] == dict(GRUPOS, edad_no_especificada=6103)


@pytest.mark.parametrize("mensaje", [
    CONFLICTO_BANDAS,
    "Los datos del municipio cambiaron mientras editabas. Recarga la página e intenta de nuevo.",
])
def test_bandas_cambiadas_por_otra_persona_es_409(cliente, admin, llamadas, mensaje):
    llamadas["respuesta"] = (False, mensaje, None)
    r = cliente.put("/api/v1/regions/39/age-groups?format=json", headers=admin, json=correccion_grupos())
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"


def test_regla_de_bandas_que_no_es_conflicto_es_422(cliente, admin, llamadas):
    llamadas["respuesta"] = (False, "La suma de las cinco bandas debe conservar la población "
                                    "con edad declarada del municipio.", None)
    r = cliente.put("/api/v1/regions/39/age-groups?format=json", headers=admin, json=correccion_grupos())
    assert r.status_code == 422


@pytest.mark.parametrize("cuerpo", [
    correccion_grupos(groups=dict(GRUPOS, **{"80+": -1})),
    correccion_grupos(groups=dict(GRUPOS, **{"0-19": "muchos"})),
    correccion_grupos(groups=[1, 2, 3]),
    correccion_grupos(reason=5),
    {"groups": GRUPOS, "reason": "Sin esperados"},
    correccion_grupos(expected_groups=dict(GRUPOS)),
    correccion_grupos(expected_groups=dict(GRUPOS, edad_no_especificada=-4)),
    correccion_grupos(expected_groups=dict(GRUPOS, edad_no_especificada=True)),
])
def test_correccion_de_grupos_invalida_es_422(cliente, admin, llamadas, cuerpo):
    r = cliente.put("/api/v1/regions/39/age-groups?format=json", headers=admin, json=cuerpo)
    assert r.status_code == 422
    assert llamadas["grupos"] == []
