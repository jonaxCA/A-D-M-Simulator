from contextlib import contextmanager
from xml.etree import ElementTree as ET

import psycopg2
import pytest

from backend_web import queries
from epidemia_comun.errores import ErrorAPI
from microservicios.enfermedades import datos as bd
from microservicios.enfermedades import rutas

LISTADO = {"enfermedades": [{"id": 1, "code": "SARS_COV_2_ANCESTRAL", "nombre": "COVID-19",
                             "activa": True, "actividad": "con_casos"}],
           "total": 1, "pagina": 1, "por_pagina": 10, "paginas": 1, "desde": 1, "hasta": 1}


class BaseFalsa:
    def __init__(self):
        self.diseases = {1: {"code": "SARS_COV_2_ANCESTRAL", "name": "COVID-19",
                             "description": None, "is_active": True}}
        self.sentencias = []
        self.commits = 0

    def ejecutar(self, sql, p):
        self.sentencias.append(sql)
        if sql.startswith("INSERT INTO diseases"):
            if any(d["code"] == p[0] for d in self.diseases.values()):
                raise psycopg2.errors.UniqueViolation("uq_diseases_code")
            nuevo = max(self.diseases) + 1
            self.diseases[nuevo] = {"code": p[0], "name": p[1], "description": p[2],
                                    "is_active": True}
            return [(nuevo,)]
        if sql.startswith("SELECT id, name, description FROM diseases"):
            d = self.diseases.get(p[0])
            return [(p[0], d["name"], d["description"])] if d else []
        if sql.startswith("SELECT is_active FROM diseases"):
            d = self.diseases.get(p[0])
            return [(d["is_active"],)] if d else []
        if sql.startswith("UPDATE diseases SET name"):
            self.diseases[p[2]].update(name=p[0], description=p[1])
        elif sql.startswith("UPDATE diseases SET is_active"):
            self.diseases[p[1]]["is_active"] = p[0]
        return []


class Cursor:
    def __init__(self, base):
        self.base, self.filas = base, []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, sql, params=()):
        self.filas = self.base.ejecutar(" ".join(sql.split()), params)

    def fetchone(self):
        return self.filas[0] if self.filas else None


class Conexion:
    def __init__(self, base):
        self.base = base

    def cursor(self):
        return Cursor(self.base)

    def commit(self):
        self.base.commits += 1


@pytest.fixture
def base(monkeypatch):
    falsa = BaseFalsa()

    @contextmanager
    def get_conn():
        yield Conexion(falsa)

    monkeypatch.setattr(rutas, "get_conn", get_conn)
    return falsa


@pytest.fixture
def bitacora(monkeypatch):
    eventos = []
    monkeypatch.setattr(rutas, "log_audit",
                        lambda ctx, accion, entidad, entity_id=None, data_before=None,
                        data_after=None, **_: eventos.append(
                            (ctx.user_id, accion, entidad, entity_id, data_before, data_after)))
    return eventos


class DefinicionesFalsas:
    """La ficha y las definiciones de caso (enfermedades.datos) en memoria, sobre la misma base falsa.
    Su SQL se prueba contra la base en test_enfermedades_bd.py."""

    def __init__(self, base, eventos):
        self.base, self.eventos = base, eventos
        self.filas = {1: [{"version": 1, "status": "vigente", "criterios": [
            {"clasificacion": "Caso sospechoso", "texto": "Fiebre y tos."}], "fuente": "DGE 2023",
            "url": None, "created_by": None, "created_at": "2026-11-23T10:00:00+00:00", "published_by": None,
            "published_at": "2026-11-23T10:00:00+00:00", "retired_at": None}]}

    def enfermedad(self, disease_id):
        d = self.base.diseases.get(disease_id)
        if d is None:
            return None
        return {"id": disease_id, "code": d["code"], "name": d["name"], "description": d["description"],
                "is_active": d["is_active"], "created_at": "2026-09-01T00:00:00",
                "transmission": d.get("transmission", "respiratoria"), "icd10": d.get("icd10", "U07.1, U07.2"),
                "classification_source": d.get("classification_source", "OMS")}

    def clasifica(self, disease_id, cambios, *, contexto):
        if disease_id not in self.base.diseases:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
        self.base.diseases[disease_id].update(cambios)
        self.eventos.append((contexto.user_id, "UPDATE", "diseases", disease_id, None, dict(cambios)))

    def definiciones(self, disease_id):
        return [dict(f) for f in reversed(self.filas.get(disease_id, []))]

    def definicion(self, disease_id, version=None):
        for f in self.filas.get(disease_id, []):
            if (version is None and f["status"] == "vigente") or f["version"] == version:
                return dict(f)
        return None

    def crea_borrador(self, disease_id, criterios, fuente, url, *, contexto):
        filas = self.filas.setdefault(disease_id, [])
        if any(f["status"] == "borrador" for f in filas):
            raise ErrorAPI(409, "CONFLICTO", "Ya hay un borrador.")
        filas.append({"version": len(filas) + 1, "status": "borrador", "criterios": criterios, "fuente": fuente,
                      "url": url, "created_by": contexto.user_id, "created_at": "2026-11-23T11:00:00+00:00",
                      "published_by": None, "published_at": None, "retired_at": None})
        self.eventos.append((contexto.user_id, "CREATE", "case_definitions", disease_id, None, None))
        return len(filas)

    def _borrador(self, disease_id, version):
        fila = self.definicion(disease_id, version)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe esa versión.")
        if fila["status"] != "borrador":
            raise ErrorAPI(409, "CONFLICTO", "Lo publicado no cambia.")
        return [f for f in self.filas[disease_id] if f["version"] == version][0]

    def edita_borrador(self, disease_id, version, criterios, fuente, url, *, contexto):
        self._borrador(disease_id, version).update(criterios=criterios, fuente=fuente, url=url)

    def publica(self, disease_id, version, *, contexto):
        fila = self._borrador(disease_id, version)
        retirada = None
        for f in self.filas[disease_id]:
            if f["status"] == "vigente":
                f.update(status="retirada", retired_at="2026-11-23T12:00:00+00:00")
                retirada = f["version"]
        fila.update(status="vigente", published_at="2026-11-23T12:00:00+00:00", published_by=contexto.user_id)
        self.eventos.append((contexto.user_id, "PUBLISH", "case_definitions", disease_id, None, None))
        return retirada


@pytest.fixture
def definiciones(monkeypatch, base, bitacora):
    falsas = DefinicionesFalsas(base, bitacora)
    for nombre in ("enfermedad", "clasifica", "definiciones", "definicion", "crea_borrador",
                   "edita_borrador", "publica"):
        monkeypatch.setattr(bd, nombre, getattr(falsas, nombre))
    return falsas


@pytest.fixture
def cliente(crear_cliente, base, bitacora, definiciones, monkeypatch):
    pedidos = []
    monkeypatch.setattr(queries, "get_enfermedades",
                        lambda **f: pedidos.append(f) or LISTADO)
    monkeypatch.setattr(queries, "get_enfermedad",
                        lambda i: {"id": 1, "code": "SARS_COV_2_ANCESTRAL", "name": "COVID-19",
                                   "description": None, "is_active": True,
                                   "created_at": "2026-09-01T00:00:00",
                                   "default_params": {}} if i == 1 else None)
    c = crear_cliente("enfermedades")
    c.pedidos = pedidos
    return c


@pytest.fixture
def epidemiologo(token):
    return token(roles=("EPIDEMIOLOGO",))


def test_lista_xml_por_omision(cliente):
    r = cliente.get("/api/v1/diseases")
    assert r.status_code == 200 and r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "catalogo_enfermedades"
    assert raiz.find("enfermedades").find("enfermedad").findtext("code") == "SARS_COV_2_ANCESTRAL"


def test_lista_xml_valido_con_letalidad_por_edad(cliente, monkeypatch):
    con_edades = {**LISTADO["enfermedades"][0],
                  "parametros": {"informativos": [{"valor": {"0-19": 0.0001, "80+": 0.08}}]}}
    monkeypatch.setattr(queries, "get_enfermedades", lambda **f: dict(LISTADO, enfermedades=[con_edades]))
    respuesta = cliente.get("/api/v1/diseases")
    assert respuesta.status_code == 200
    raiz = ET.fromstring(respuesta.data)
    assert raiz.find(".//entrada[@clave='0-19']").text == "0.0001"
    assert raiz.find(".//entrada[@clave='80+']").text == "0.08"


def test_lista_json_con_format_y_con_accept(cliente):
    assert cliente.get("/api/v1/diseases?format=json").get_json()["total"] == 1
    r = cliente.get("/api/v1/diseases", headers={"Accept": "application/json"})
    assert r.content_type.startswith("application/json")


def test_format_invalido_es_400(cliente):
    r = cliente.get("/api/v1/diseases?format=yaml")
    assert r.status_code == 400
    assert r.content_type.startswith("application/problem")


def test_lista_pasa_los_filtros(cliente):
    cliente.get("/api/v1/diseases?q=covid&status=activa&page=2&size=5&format=json")
    assert cliente.pedidos == [{"busqueda": "covid", "estado": "activa", "pagina": 2, "por_pagina": 5}]


@pytest.mark.parametrize("consulta", ["size=101", "page=0", "status=borrada", "size=x"])
def test_filtros_invalidos_son_422(cliente, consulta):
    assert cliente.get("/api/v1/diseases?format=json&" + consulta).status_code == 422


# --- exportar (F-3): la misma lista, con sesión y su EXPORT en la bitácora ----------------

def test_exportar_pide_sesion(cliente, bitacora):
    assert cliente.get("/api/v1/diseases/export?format=json").status_code == 401
    assert bitacora == []


def test_exportar_anota_un_export_con_quien_lo_pidio(cliente, bitacora, epidemiologo):
    r = cliente.get("/api/v1/diseases/export?format=json", headers=epidemiologo)
    assert r.status_code == 200 and r.get_json() == LISTADO
    assert len(bitacora) == 1
    usuario, accion, entidad, entity_id, _, _ = bitacora[0]
    assert (accion, entidad, entity_id) == ("EXPORT", "reports", "catalogo_enfermedades")
    assert usuario is not None


def test_exportar_pasa_los_filtros_y_solo_anota_la_primera_pagina(cliente, bitacora, epidemiologo):
    # Una descarga de varias páginas es un solo EXPORT.
    cliente.get("/api/v1/diseases/export?q=covid&status=activa&page=2&size=5&format=json",
                headers=epidemiologo)
    assert cliente.pedidos == [{"busqueda": "covid", "estado": "activa", "pagina": 2, "por_pagina": 5}]
    assert bitacora == []


@pytest.mark.parametrize("consulta", ["size=101", "page=0", "status=borrada"])
def test_exportar_con_filtros_invalidos_es_422(cliente, bitacora, epidemiologo, consulta):
    r = cliente.get("/api/v1/diseases/export?format=json&" + consulta, headers=epidemiologo)
    assert r.status_code == 422 and bitacora == []


def test_detalle_y_no_encontrado(cliente):
    datos = cliente.get("/api/v1/diseases/1?format=json").get_json()
    assert datos["code"] == "SARS_COV_2_ANCESTRAL" and "default_params" not in datos
    r = cliente.get("/api/v1/diseases/99?format=json")
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"


def test_escritura_sin_token_401_y_analista_403(cliente, token):
    cuerpo = {"code": "DENGUE", "name": "Dengue"}
    assert cliente.post("/api/v1/diseases?format=json", json=cuerpo).status_code == 401
    r = cliente.post("/api/v1/diseases?format=json", json=cuerpo, headers=token(roles=("ANALISTA",)))
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


def test_alta_en_json_audita(cliente, epidemiologo, base, bitacora):
    r = cliente.post("/api/v1/diseases?format=json", headers=epidemiologo,
                     json={"code": "DENGUE", "name": " Dengue ", "description": "Arbovirosis"})
    assert r.status_code == 201
    nuevo = r.get_json()["id"]
    assert base.diseases[nuevo]["name"] == "Dengue" and base.commits == 1
    assert bitacora == [(7, "CREATE", "diseases", nuevo, None, {"code": "DENGUE", "name": "Dengue"})]


def test_alta_en_xml(cliente, epidemiologo, base):
    r = cliente.post("/api/v1/diseases?format=json", headers={**epidemiologo, "Content-Type": "application/xml"},
                     data=b"<solicitud><code>INFLUENZA_B</code><name>Influenza B</name></solicitud>")
    assert r.status_code == 201
    assert base.diseases[r.get_json()["id"]]["code"] == "INFLUENZA_B"


@pytest.mark.parametrize("cuerpo", [
    {"code": "dengue", "name": "Dengue"},
    {"code": "DENGUE"},
    {"code": "DENGUE", "name": "Dengue", "default_params": {}},
    {"code": 5, "name": "Dengue"},
])
def test_alta_invalida_es_422(cliente, epidemiologo, base, cuerpo):
    r = cliente.post("/api/v1/diseases?format=json", headers=epidemiologo, json=cuerpo)
    assert r.status_code == 422
    assert not any(s.startswith("INSERT") for s in base.sentencias)


def test_codigo_duplicado_es_409(cliente, epidemiologo):
    r = cliente.post("/api/v1/diseases?format=json", headers=epidemiologo,
                     json={"code": "SARS_COV_2_ANCESTRAL", "name": "Otra"})
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"


def test_cuerpo_que_no_es_json_ni_xml(cliente, epidemiologo):
    r = cliente.post("/api/v1/diseases?format=json", headers={**epidemiologo, "Content-Type": "text/plain"},
                     data=b"code=DENGUE")
    assert r.status_code == 415


def test_editar_no_cambia_el_codigo(cliente, epidemiologo, base, bitacora):
    r = cliente.put("/api/v1/diseases/1?format=json", headers=epidemiologo,
                    json={"code": "OTRO", "name": "COVID-19"})
    assert r.status_code == 422
    r = cliente.put("/api/v1/diseases/1?format=json", headers=epidemiologo,
                    json={"name": "COVID-19 (ancestral)", "description": "Variante original"})
    assert r.status_code == 200
    assert base.diseases[1]["code"] == "SARS_COV_2_ANCESTRAL"
    assert bitacora[-1][1:4] == ("UPDATE", "diseases", 1)
    assert bitacora[-1][5]["name"] == "COVID-19 (ancestral)"


def test_editar_inexistente_es_404(cliente, epidemiologo):
    r = cliente.put("/api/v1/diseases/99?format=json", headers=epidemiologo, json={"name": "X"})
    assert r.status_code == 404


def test_desactivar_es_baja_logica(cliente, epidemiologo, base, bitacora):
    r = cliente.post("/api/v1/diseases/1/deactivate?format=json", headers=epidemiologo)
    assert r.status_code == 200 and r.get_json()["is_active"] is False
    assert base.diseases[1]["is_active"] is False
    assert not any(s.startswith("DELETE") for s in base.sentencias)
    assert bitacora[-1][4:] == ({"is_active": True}, {"is_active": False})
    assert cliente.post("/api/v1/diseases/1/activate?format=json", headers=epidemiologo).get_json()["is_active"]


def test_accion_desconocida_es_404(cliente, epidemiologo):
    assert cliente.post("/api/v1/diseases/1/delete?format=json", headers=epidemiologo).status_code == 404


def test_no_hay_ruta_delete(cliente, epidemiologo):
    assert cliente.delete("/api/v1/diseases/1?format=json", headers=epidemiologo).status_code == 405


@pytest.fixture
def conteos(monkeypatch):
    consultas = []

    def query(sql, params=(), one=False):
        consultas.append((" ".join(sql.split()), params))
        if "FROM diseases" in sql:
            return {"registradas": 9, "activas": 7, "inactivas": 2, "altas_30d": 1}
        return {"n": 3}
    monkeypatch.setattr(rutas, "query", query)
    return consultas


def test_estadisticas_publicas_en_json_y_xml(cliente, conteos):
    from pathlib import Path
    import xmlschema
    r = cliente.get("/api/v1/diseases/stats?format=json")
    assert r.status_code == 200
    assert r.get_json() == {"registradas": 9, "activas": 7, "inactivas": 2, "altas_30d": 1,
                            "detectadas_30d": 3}
    sql, params = conteos[1]
    assert "c.status IN ('pendiente', 'validado')" in sql and params == ("19",)
    xsd = Path(__file__).resolve().parents[3] / "docs/contratos/enfermedades/enfermedad.xsd"
    xmlschema.XMLSchema(str(xsd)).validate(cliente.get("/api/v1/diseases/stats").data.decode("utf-8"))


def test_estadisticas_no_chocan_con_el_detalle(cliente, conteos):
    assert cliente.get("/api/v1/diseases/1?format=json").get_json()["id"] == 1
    assert cliente.get("/api/v1/diseases/stats?format=json").status_code == 200



# ---- clasificación y definiciones de caso (D58) ------------------------------------------------

DEFINICION = {"criterios": [{"clasificacion": "Caso probable", "texto": "Fiebre y dos signos."},
                            {"clasificacion": "Caso confirmado", "texto": "Con RT-PCR positiva."}],
              "fuente": "DGE, marzo de 2021, p. 60", "url": "https://epidemiologia.salud.gob.mx/x.pdf"}


def test_la_ficha_trae_la_clasificacion(cliente):
    datos = cliente.get("/api/v1/diseases/1?format=json").get_json()
    assert (datos["transmission"], datos["icd10"]) == ("respiratoria", "U07.1, U07.2")
    assert datos["classification_source"] == "OMS"


def test_clasificar_exige_fuente_y_una_via_valida(cliente, epidemiologo, base):
    r = cliente.put("/api/v1/diseases/1?format=json", headers=epidemiologo,
                    json={"name": "COVID-19", "transmission": "respiratoria", "icd10": "U07.1"})
    assert r.status_code == 422 and "fuente" in r.get_json()["detail"]
    r = cliente.put("/api/v1/diseases/1?format=json", headers=epidemiologo,
                    json={"name": "COVID-19", "transmission": "aerea", "classification_source": "X"})
    assert r.status_code == 422
    r = cliente.put("/api/v1/diseases/1?format=json", headers=epidemiologo,
                    json={"name": "COVID-19", "transmission": "respiratoria", "icd10": "U07.1",
                          "classification_source": "OMS, CIE-10 de emergencia"})
    assert r.status_code == 200 and base.diseases[1]["icd10"] == "U07.1"


def test_las_definiciones_son_publicas(cliente):
    lista = cliente.get("/api/v1/diseases/1/case-definitions?format=json").get_json()
    assert lista["total"] == 1 and lista["definiciones"][0]["status"] == "vigente"
    vigente = cliente.get("/api/v1/diseases/1/case-definitions/current?format=json").get_json()
    assert vigente["version"] == 1 and vigente["criterios"][0]["clasificacion"] == "Caso sospechoso"
    assert cliente.get("/api/v1/diseases/1/case-definitions/1?format=json").status_code == 200
    assert cliente.get("/api/v1/diseases/1/case-definitions/7?format=json").status_code == 404
    assert cliente.get("/api/v1/diseases/99/case-definitions?format=json").status_code == 404
    assert cliente.get("/api/v1/diseases/99/case-definitions/current?format=json").status_code == 404
    raiz = ET.fromstring(cliente.get("/api/v1/diseases/1/case-definitions").data)
    assert raiz.find("definiciones/definicion/criterios/criterio/clasificacion").text == "Caso sospechoso"


def test_borrador_edicion_y_publicacion(cliente, epidemiologo, bitacora):
    r = cliente.post("/api/v1/diseases/1/case-definitions?format=json", headers=epidemiologo, json=DEFINICION)
    assert r.status_code == 201 and r.get_json()["version"] == 2 and r.get_json()["status"] == "borrador"
    assert cliente.post("/api/v1/diseases/1/case-definitions?format=json", headers=epidemiologo,
                        json=DEFINICION).status_code == 409
    r = cliente.put("/api/v1/diseases/1/case-definitions/2?format=json", headers=epidemiologo,
                    json=dict(DEFINICION, fuente="DGE, marzo de 2021, pp. 60-61"))
    assert r.status_code == 200 and r.get_json()["fuente"].endswith("60-61")
    r = cliente.post("/api/v1/diseases/1/case-definitions/2/publish?format=json", headers=epidemiologo)
    assert r.status_code == 200 and r.get_json()["status"] == "vigente" and r.get_json()["retirada"] == 1
    assert cliente.get("/api/v1/diseases/1/case-definitions/1?format=json").get_json()["status"] == "retirada"
    assert cliente.put("/api/v1/diseases/1/case-definitions/2?format=json", headers=epidemiologo,
                       json=DEFINICION).status_code == 409
    assert [e[1] for e in bitacora if e[2] == "case_definitions"] == ["CREATE", "PUBLISH"]


def test_definicion_en_xml(cliente, epidemiologo):
    xml = ("<definicion><criterios><criterio><clasificacion>Caso probable</clasificacion>"
           "<texto>Fiebre.</texto></criterio></criterios><fuente>DGE 2021</fuente></definicion>")
    r = cliente.post("/api/v1/diseases/1/case-definitions?format=json",
                     headers={**epidemiologo, "Content-Type": "application/xml"}, data=xml.encode("utf-8"))
    assert r.status_code == 201 and r.get_json()["criterios"] == [{"clasificacion": "Caso probable", "texto": "Fiebre."}]


@pytest.mark.parametrize("cuerpo,mensaje", [
    ({"criterios": [], "fuente": "DGE"}, "lista"),
    ({"criterios": [{"clasificacion": "X"}], "fuente": "DGE"}, "clasificacion y texto"),
    ({"criterios": DEFINICION["criterios"]}, "fuente"),
    (dict(DEFINICION, url="ftp://x"), "url"),
    (dict(DEFINICION, version=3), "Solo se aceptan"),
])
def test_una_definicion_invalida_es_422(cliente, epidemiologo, cuerpo, mensaje):
    r = cliente.post("/api/v1/diseases/1/case-definitions?format=json", headers=epidemiologo, json=cuerpo)
    assert r.status_code == 422 and mensaje in r.get_json()["detail"]


def test_solo_epidemiologo_y_admin_escriben_definiciones(cliente, token):
    assert cliente.post("/api/v1/diseases/1/case-definitions?format=json", json=DEFINICION).status_code == 401
    r = cliente.post("/api/v1/diseases/1/case-definitions?format=json", json=DEFINICION,
                     headers=token(roles=("ANALISTA",)))
    assert r.status_code == 403
    r = cliente.post("/api/v1/diseases/1/case-definitions/1/publish?format=json", headers=token(roles=("CAPTURISTA",)))
    assert r.status_code == 403
    r = cliente.post("/api/v1/diseases/1/case-definitions?format=json", json=DEFINICION,
                     headers=token(roles=("ADMINISTRADOR",)))
    assert r.status_code == 201
