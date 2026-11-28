import hashlib
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from epidemia_comun import archivos
from microservicios.evidencias import datos as evidencias
from microservicios.evidencias import reportes, rutas

RAIZ = Path(__file__).resolve().parents[3]
PROPIO, AJENO = 418, 500       # el 418 lo reportó quien firma el token (sub 7); el 500, la cuenta 8
CORRIDAS = {12, 15, 20}
JPEG = b"\xff\xd8\xff\xe0" + b"foto" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"otra" * 16
PDF = b"%PDF-1.7\n" + b"reporte" * 16
FECHA = datetime(2026, 11, 1, 17, tzinfo=timezone.utc)


def caido(*args, **kwargs):
    raise archivos.BucketNoDisponible("ConnectionError")


class Mundo:
    """datos.py y reportes.py simulados; los archivos van de verdad a archivos (en disco)."""

    def __init__(self):
        self.casos = {PROPIO: {"id": PROPIO, "reported_by": 7}, AJENO: {"id": AJENO, "reported_by": 8}}
        self.filas, self.objetos, self.guardadas, self.borradas = {}, {}, [], []
        self.reportes, self.objetos_reportes, self.reportes_guardados = {}, {}, []

    def get_caso(self, case_id):
        return dict(self.casos[case_id]) if case_id in self.casos else None

    def guardar_evidencia(self, case_id, datos, user_id, *, contexto):
        self.guardadas.append((case_id, user_id, contexto.user_id))
        huella = hashlib.sha256(datos).hexdigest()
        previa = next((f for f in self.filas.values()
                       if f["case_id"] == case_id and f["sha256"] == huella), None)
        if previa:
            return dict(previa), False
        evidencia_id = len(self.filas) + 1
        objeto = "evidencias/%d/%d.bin" % (case_id, evidencia_id)
        archivos.guardar(objeto, datos, "application/octet-stream")
        self.filas[evidencia_id] = {
            "id": evidencia_id, "case_id": case_id, "mime_type": evidencias.tipo_por_contenido(datos),
            "size_bytes": len(datos), "sha256": huella, "privacy": "privado", "uploaded_by": user_id,
            "uploaded_at": FECHA}
        self.objetos[evidencia_id] = objeto
        return dict(self.filas[evidencia_id]), True

    def listar_evidencias(self, case_id):
        return [dict(f) for f in self.filas.values() if f["case_id"] == case_id]

    def get_evidencia(self, evidencia_id):
        return dict(self.filas[evidencia_id]) if evidencia_id in self.filas else None

    def objeto_de_evidencia(self, evidencia_id):
        if evidencia_id not in self.filas:
            return None, None
        return dict(self.filas[evidencia_id]), self.objetos[evidencia_id]

    def borrar_evidencia(self, evidencia_id, *, contexto):
        self.borradas.append((evidencia_id, contexto.user_id))
        return self.filas.pop(evidencia_id, None)

    def corridas_que_faltan(self, run_ids):
        return [r for r in run_ids if r not in CORRIDAS]

    def guardar_reporte(self, run_ids, datos, titulo, user_id, *, contexto):
        self.reportes_guardados.append((run_ids, titulo, user_id, contexto.user_id))
        huella = hashlib.sha256(datos).hexdigest()
        previo = next((f for f in self.reportes.values()
                       if f["run_ids"] == run_ids and f["sha256"] == huella), None)
        if previo:
            return dict(previo), False
        reporte_id = len(self.reportes) + 1
        objeto = "reportes/%d/%d.pdf" % (run_ids[0], reporte_id)
        archivos.guardar(objeto, datos, "application/pdf")
        self.reportes[reporte_id] = {
            "id": reporte_id, "run_ids": run_ids, "title": titulo, "mime_type": "application/pdf",
            "size_bytes": len(datos), "sha256": huella, "privacy": "privado", "uploaded_by": user_id,
            "uploaded_at": FECHA}
        self.objetos_reportes[reporte_id] = objeto
        return dict(self.reportes[reporte_id]), True

    def listar_reportes(self, run_ids=None):
        return [dict(f) for f in self.reportes.values()
                if not run_ids or set(run_ids) <= set(f["run_ids"])]

    def get_reporte(self, reporte_id):
        return dict(self.reportes[reporte_id]) if reporte_id in self.reportes else None

    def objeto_de_reporte(self, reporte_id):
        if reporte_id not in self.reportes:
            return None, None
        return dict(self.reportes[reporte_id]), self.objetos_reportes[reporte_id]

    def borrar_reporte(self, reporte_id, *, contexto):
        return self.reportes.pop(reporte_id, None)


@pytest.fixture
def mundo(monkeypatch, tmp_path):
    monkeypatch.setenv("ARCHIVOS", "disco")
    monkeypatch.setenv("ARCHIVOS_DIR", str(tmp_path))
    m = Mundo()
    for nombre in ("get_caso", "guardar_evidencia", "listar_evidencias", "get_evidencia",
                   "objeto_de_evidencia", "borrar_evidencia"):
        monkeypatch.setattr(evidencias, nombre, getattr(m, nombre))
    for nombre in ("corridas_que_faltan", "guardar_reporte", "listar_reportes", "get_reporte",
                   "objeto_de_reporte", "borrar_reporte"):
        monkeypatch.setattr(reportes, nombre, getattr(m, nombre))
    return m


@pytest.fixture
def firmadas(monkeypatch):
    pedidas = []

    def url_firmada(objeto, minutos=archivos.MINUTOS, nombre=None):
        pedidas.append((objeto, nombre))
        return ("http://localhost:4443/epidemia-archivos/%s?X-Goog-Expires=900" % objeto,
                datetime(2026, 11, 1, 17, 15, tzinfo=timezone.utc))
    monkeypatch.setattr(archivos, "url_firmada", url_firmada)
    return pedidas


@pytest.fixture
def bucket_caido(monkeypatch):
    for nombre in ("guardar", "leer", "url_firmada"):
        monkeypatch.setattr(archivos, nombre, caido)


@pytest.fixture
def cliente(crear_cliente, mundo):
    return crear_cliente("evidencias")


@pytest.fixture
def capturista(token):
    return token(("CAPTURISTA",))


@pytest.fixture
def analista(token):
    return token(("ANALISTA",))


def subir(cliente, cabeceras, datos=JPEG, caso=PROPIO, tipo="image/jpeg", huella=None):
    if huella:
        cabeceras = dict(cabeceras, **{"X-Content-SHA256": huella})
    return cliente.post("/api/v1/cases/%d/attachments?format=json" % caso, data=datos,
                        headers=cabeceras, content_type=tipo)


def subir_reporte(cliente, cabeceras, datos=PDF, consulta="runs=12,15", huella=None):
    if huella:
        cabeceras = dict(cabeceras, **{"X-Content-SHA256": huella})
    return cliente.post("/api/v1/reports?format=json&" + consulta, data=datos, headers=cabeceras,
                        content_type="application/pdf")


# ---- subir una evidencia ----------------------------------------------------------------

def test_sin_token_es_401(cliente):
    assert cliente.post("/api/v1/cases/%d/attachments" % PROPIO, data=JPEG).status_code == 401


# El ADMINISTRADOR tampoco captura (D1).
@pytest.mark.parametrize("rol", ["ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR"])
def test_quien_no_captura_no_sube(cliente, token, mundo, rol):
    assert subir(cliente, token((rol,))).status_code == 403
    assert mundo.guardadas == []


def test_quien_reporto_el_caso_sube_al_bucket_y_el_reintento_no_duplica(cliente, capturista, mundo):
    r = subir(cliente, capturista)
    assert r.status_code == 201
    assert r.get_json()["mime_type"] == "image/jpeg" and r.get_json()["case_id"] == PROPIO
    assert mundo.guardadas == [(PROPIO, 7, 7)]
    assert archivos.leer(mundo.objetos[1]) == JPEG
    r = subir(cliente, capturista)
    assert r.status_code == 200 and r.get_json()["id"] == 1


def test_el_tipo_sale_del_contenido_no_del_encabezado(cliente, capturista):
    r = subir(cliente, capturista, datos=PNG, tipo="image/jpeg")
    assert r.status_code == 201 and r.get_json()["mime_type"] == "image/png"
    assert subir(cliente, capturista, datos=JPEG, tipo="application/octet-stream").status_code == 201


def test_el_caso_de_otra_persona_no_recibe_evidencias(cliente, capturista, mundo):
    r = subir(cliente, capturista, caso=AJENO)
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"
    assert mundo.guardadas == []


@pytest.mark.parametrize("datos,tipo", [(b"", "image/jpeg"), (b"GIF89a" + b"x" * 20, "image/gif"),
                                        (b"MZ ejecutable", "application/octet-stream"),
                                        (b"--x\r\nContent-Disposition: form-data; name=\"foto\"\r\n\r\n",
                                         "multipart/form-data; boundary=x")])
def test_archivo_invalido_es_422(cliente, capturista, mundo, datos, tipo):
    r = subir(cliente, capturista, datos=datos, tipo=tipo)
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert mundo.guardadas == []


def test_mas_de_20_mb_es_413(cliente, capturista, mundo, monkeypatch):
    monkeypatch.setattr(evidencias, "MAXIMO", len(JPEG) - 1)
    assert subir(cliente, capturista).status_code == 413
    assert mundo.guardadas == []


def test_la_huella_que_declara_el_cliente_se_revisa(cliente, capturista, mundo):
    otra = hashlib.sha256(PNG).hexdigest()
    r = subir(cliente, capturista, huella=otra)
    assert r.status_code == 422 and "huella" in r.get_json()["detail"]
    assert subir(cliente, capturista, huella="no-es-hex").status_code == 422
    assert mundo.guardadas == []
    assert subir(cliente, capturista, huella=hashlib.sha256(JPEG).hexdigest().upper()).status_code == 201


def test_caso_inexistente_es_404_y_id_invalido_422(cliente, capturista):
    assert subir(cliente, capturista, caso=999).status_code == 404
    r = cliente.post("/api/v1/cases/x/attachments", data=JPEG, headers=capturista)
    assert r.status_code == 422


def test_bucket_caido_es_503_y_no_queda_nada(cliente, capturista, mundo, bucket_caido):
    r = subir(cliente, capturista)
    assert r.status_code == 503 and r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
    assert r.headers["Retry-After"] == "5"
    assert mundo.filas == {}


# ---- consultar, abrir y borrar una evidencia ---------------------------------------------

@pytest.mark.parametrize("rol", rutas.ROLES_LEEN)
def test_los_que_leen_casos_ven_las_evidencias(cliente, capturista, token, rol):
    subir(cliente, capturista)
    subir(cliente, capturista, datos=PNG)
    r = cliente.get("/api/v1/cases/%d/attachments?format=json" % PROPIO, headers=token((rol,)))
    assert r.status_code == 200 and r.get_json()["total"] == 2
    assert cliente.get("/api/v1/attachments/1", headers=token((rol,))).status_code == 200


def test_lista_en_xml_con_un_elemento_por_evidencia(cliente, capturista):
    subir(cliente, capturista)
    raiz = ET.fromstring(cliente.get("/api/v1/cases/%d/attachments" % PROPIO, headers=capturista).data)
    assert raiz.tag == "evidencias_caso"
    assert [e.findtext("mime_type") for e in raiz.findall("evidencias/evidencia")] == ["image/jpeg"]


def test_url_firmada_de_una_evidencia(cliente, capturista, token, mundo, firmadas):
    subir(cliente, capturista)
    r = cliente.get("/api/v1/attachments/1/url?format=json", headers=token(("EPIDEMIOLOGO",)))
    assert r.status_code == 200 and r.headers["Cache-Control"] == "private, no-store"
    datos = r.get_json()
    assert datos["id"] == 1 and datos["minutes"] == 15
    assert datos["url"].startswith("http://localhost:4443/epidemia-archivos/evidencias/418/")
    assert datos["expires_at"] == "2026-11-01T17:15:00+00:00"
    assert firmadas == [(mundo.objetos[1], "evidencia-1.jpg")]
    raiz = ET.fromstring(cliente.get("/api/v1/attachments/1/url", headers=capturista).data)
    assert raiz.tag == "url_firmada" and raiz.findtext("minutes") == "15"


def test_url_firmada_sin_permiso_sin_evidencia_o_sin_bucket(cliente, capturista, token, firmadas,
                                                            monkeypatch):
    subir(cliente, capturista)
    assert cliente.get("/api/v1/attachments/1/url", headers=token(("INVESTIGADOR",))).status_code == 403
    assert cliente.get("/api/v1/attachments/9/url", headers=capturista).status_code == 404
    monkeypatch.setattr(archivos, "url_firmada", caido)
    assert cliente.get("/api/v1/attachments/1/url", headers=capturista).status_code == 503


def test_descargar_regresa_el_archivo_tal_cual(cliente, capturista, token):
    subir(cliente, capturista)
    r = cliente.get("/api/v1/attachments/1/content", headers=token(("EPIDEMIOLOGO",)))
    assert r.status_code == 200 and r.data == JPEG and r.mimetype == "image/jpeg"
    assert r.headers["Content-Disposition"] == 'inline; filename="evidencia-1.jpg"'
    assert r.headers["Cache-Control"] == "private, no-store"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_descargar_sin_archivo_o_sin_evidencia_es_404(cliente, capturista, mundo):
    subir(cliente, capturista)
    archivos.borrar(mundo.objetos[1])
    assert cliente.get("/api/v1/attachments/1/content", headers=capturista).status_code == 404
    assert cliente.get("/api/v1/attachments/9/content", headers=capturista).status_code == 404
    assert cliente.get("/api/v1/attachments/9", headers=capturista).status_code == 404


def test_descargar_con_el_bucket_caido_es_503(cliente, capturista, monkeypatch):
    subir(cliente, capturista)
    monkeypatch.setattr(archivos, "leer", caido)
    assert cliente.get("/api/v1/attachments/1/content", headers=capturista).status_code == 503


def test_solo_administrador_borra(cliente, capturista, token, mundo):
    subir(cliente, capturista)
    assert cliente.delete("/api/v1/attachments/1", headers=capturista).status_code == 403
    r = cliente.delete("/api/v1/attachments/1?format=json", headers=token(("ADMINISTRADOR",)))
    assert r.status_code == 200 and r.get_json()["id"] == 1
    assert mundo.borradas == [(1, 7)]
    assert cliente.delete("/api/v1/attachments/1", headers=token(("ADMINISTRADOR",))).status_code == 404


# ---- reportes de una comparación (D35) ----------------------------------------------------

@pytest.mark.parametrize("rol", rutas.ROLES_SUBEN_REPORTES)
def test_analista_y_administrador_suben_el_reporte(cliente, token, mundo, rol):
    r = subir_reporte(cliente, token((rol,)), consulta="runs=12,15,12&title=%20Comparaci%C3%B3n%20A%20")
    assert r.status_code == 201
    datos = r.get_json()
    assert datos["run_ids"] == [12, 15] and datos["title"] == "Comparación A"
    assert datos["mime_type"] == "application/pdf" and datos["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert archivos.leer(mundo.objetos_reportes[1]) == PDF
    r = subir_reporte(cliente, token((rol,)), consulta="runs=12,15")
    assert r.status_code == 200 and r.get_json()["id"] == 1


@pytest.mark.parametrize("rol", ["CAPTURISTA", "EPIDEMIOLOGO", "INVESTIGADOR", "AUTORIDAD_SANITARIA"])
def test_los_demas_no_suben_reportes(cliente, token, mundo, rol):
    assert subir_reporte(cliente, token((rol,))).status_code == 403
    assert mundo.reportes_guardados == []


@pytest.mark.parametrize("consulta", ["", "runs=", "runs=a,b", "runs=0", "runs=12&title=" + "x" * 201,
                                      "runs=" + ",".join(map(str, range(1, 102)))])
def test_corridas_o_titulo_invalidos_son_422(cliente, analista, mundo, consulta):
    r = subir_reporte(cliente, analista, consulta=consulta)
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert mundo.reportes_guardados == []


def test_corridas_que_no_existen_son_422(cliente, analista, mundo):
    r = subir_reporte(cliente, analista, consulta="runs=12,99,98")
    assert r.status_code == 422 and "99, 98" in r.get_json()["detail"]
    assert mundo.reportes_guardados == []


@pytest.mark.parametrize("datos", [JPEG, b"", b"texto"])
def test_un_reporte_solo_es_pdf(cliente, analista, mundo, datos):
    r = subir_reporte(cliente, analista, datos=datos)
    assert r.status_code == 422 and mundo.reportes_guardados == []


def test_reporte_con_huella_distinta_o_bucket_caido(cliente, analista, mundo, monkeypatch):
    r = subir_reporte(cliente, analista, huella=hashlib.sha256(JPEG).hexdigest())
    assert r.status_code == 422 and mundo.reportes_guardados == []
    monkeypatch.setattr(archivos, "guardar", caido)
    assert subir_reporte(cliente, analista).status_code == 503
    assert mundo.reportes == {}


@pytest.mark.parametrize("rol", rutas.ROLES_LEEN_REPORTES)
def test_quien_lee_reportes_los_lista_y_los_abre(cliente, analista, token, firmadas, rol):
    subir_reporte(cliente, analista)
    subir_reporte(cliente, analista, datos=PDF + b"v2", consulta="runs=20")
    cabeceras = token((rol,))
    r = cliente.get("/api/v1/reports?format=json", headers=cabeceras)
    assert r.status_code == 200 and r.get_json()["total"] == 2
    r = cliente.get("/api/v1/reports?format=json&runs=15", headers=cabeceras)
    assert [f["id"] for f in r.get_json()["reportes"]] == [1]
    assert cliente.get("/api/v1/reports/1", headers=cabeceras).status_code == 200
    r = cliente.get("/api/v1/reports/1/url?format=json", headers=cabeceras)
    assert r.status_code == 200 and r.get_json()["url"].startswith(
        "http://localhost:4443/epidemia-archivos/reportes/12/")
    assert firmadas[-1][1] == "reporte-1.pdf"


def test_capturista_no_ve_reportes(cliente, capturista, analista):
    subir_reporte(cliente, analista)
    for ruta in ("/api/v1/reports", "/api/v1/reports/1", "/api/v1/reports/1/url"):
        assert cliente.get(ruta, headers=capturista).status_code == 403


def test_reportes_en_xml_y_los_que_no_existen(cliente, analista):
    subir_reporte(cliente, analista)
    raiz = ET.fromstring(cliente.get("/api/v1/reports", headers=analista).data)
    assert raiz.tag == "reportes"
    [reporte] = raiz.findall("reportes/reporte")
    assert [c.text for c in reporte.findall("run_ids/run_id")] == ["12", "15"]
    assert cliente.get("/api/v1/reports/9", headers=analista).status_code == 404
    assert cliente.get("/api/v1/reports/9/url", headers=analista).status_code == 404
    assert cliente.get("/api/v1/reports?runs=x", headers=analista).status_code == 422


def test_solo_administrador_borra_reportes(cliente, analista, token, mundo):
    subir_reporte(cliente, analista)
    assert cliente.delete("/api/v1/reports/1", headers=analista).status_code == 403
    r = cliente.delete("/api/v1/reports/1?format=json", headers=token(("ADMINISTRADOR",)))
    assert r.status_code == 200 and r.get_json()["id"] == 1
    assert cliente.delete("/api/v1/reports/1", headers=token(("ADMINISTRADOR",))).status_code == 404


# ---- comunes -------------------------------------------------------------------------------

def test_redis_caido_es_503(cliente, capturista, apagar_redis):
    apagar_redis()
    assert cliente.get("/api/v1/attachments/1", headers=capturista).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/evidencias/openapi.json").read_bytes()
