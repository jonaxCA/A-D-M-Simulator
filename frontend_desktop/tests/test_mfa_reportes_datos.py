"""Bloque A: segundo paso del login (D40, D41), reporte al bucket (RF-F17, D35) y gestión de datos (D6, D53)."""
import hashlib
import os

import pytest

from frontend_desktop.app import api, config, servicios, xmlio
from frontend_desktop.tests.test_api import Respuesta, problema

# El ejemplo del contrato de estado-servicios no lista evidencias ni importacion; el sondeo sí los anuncia.
DIRECTORIO = xmlio.escribir({"servicios": [{"nombre": n, "url": "http://%s" % n} for n in (
    "auth", "sesiones", "usuarios", "escenarios", "evidencias", "importacion")]}, "directorio")


def ejemplo(servicio, nombre):
    return (config.CONTRATOS / servicio / "ejemplos" / (nombre + ".xml")).read_bytes()


SESION_ACTUAL = ejemplo("sesiones", "sesion_actual")
PERFIL = ejemplo("usuarios", "consultar_perfil")


class HTTP:
    """Como HTTPFalso de test_api, pero guarda también los parámetros."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def get(self, url, **_):
        return Respuesta(200, DIRECTORIO)

    def request(self, metodo, url, data=None, params=None, headers=None, timeout=None):
        self.llamadas.append({"metodo": metodo, "ruta": url.split("/api/v1/")[1], "cuerpo": data,
                              "params": params, "headers": headers})
        return self.respuestas.pop(0)


def cliente(*respuestas, sesion=True):
    c = api.Cliente("http://directorio", HTTP(*respuestas))
    if sesion:
        c.access, c.refresh = "acceso", "renovacion"
    return c


def cuerpo(llamada):
    return xmlio.leer(llamada["cuerpo"])


# --- Segundo paso del login (D40) ---------------------------------------------------------------

def test_perfil_critico_recibe_el_reto_sin_tokens():
    c = cliente(Respuesta(200, ejemplo("auth", "iniciar_sesion_mfa")), sesion=False)
    reto = servicios.abrir_sesion(c, "admin", "Epidemia2026!", "cap", "7")
    assert reto["mfa_requerido"] is True and reto["mfa_token"] == "MFA_TOKEN_DE_EJEMPLO"
    assert reto["mfa_enrolado"] is False
    assert c.access is None and c.refresh is None
    assert [x["ruta"] for x in c.http.llamadas] == ["auth/login"]


def test_verificar_el_codigo_abre_la_sesion_y_revisa_el_rol():
    c = cliente(Respuesta(200, ejemplo("auth", "mfa_verificar")), Respuesta(200, SESION_ACTUAL),
                Respuesta(200, PERFIL), sesion=False)
    datos = servicios.segundo_paso(c, "verify", "MFA_TOKEN_DE_EJEMPLO", codigo="123456")
    verificar = c.http.llamadas[0]
    assert verificar["ruta"] == "auth/mfa/verify" and "Authorization" not in verificar["headers"]
    assert cuerpo(verificar) == {"mfa_token": "MFA_TOKEN_DE_EJEMPLO", "codigo": "123456"}
    assert c.access == "JWT_DE_EJEMPLO" and c.refresh == "REFRESH_DE_EJEMPLO"
    assert [x["ruta"] for x in c.http.llamadas[1:]] == ["sessions/current", "users/me"]
    assert datos["codigos_respaldo"] == []
    assert set(c.roles()) & set(config.ROLES_PERMITIDOS)


def test_enrolar_regresa_el_secreto_y_confirmar_los_respaldos():
    c = cliente(Respuesta(200, ejemplo("auth", "mfa_enrolar")), Respuesta(200, ejemplo("auth", "mfa_confirmar")),
                Respuesta(200, SESION_ACTUAL), Respuesta(200, PERFIL), sesion=False)
    secreto = servicios.segundo_paso(c, "enroll", "T", codigo_alta="alta-1")
    assert secreto["secreto"].startswith("JBSWY3DP") and secreto["uri"].startswith("otpauth://totp/")
    assert cuerpo(c.http.llamadas[0]) == {"mfa_token": "T", "codigo_alta": "alta-1"}
    assert c.access is None
    datos = servicios.segundo_paso(c, "confirm", "T", codigo="654321")
    assert c.http.llamadas[1]["ruta"] == "auth/mfa/confirm"
    assert datos["codigos_respaldo"] == ["CODIGO-DE-RESPALDO-1", "CODIGO-DE-RESPALDO-2"]
    assert c.access == "JWT_DE_EJEMPLO"


def test_codigo_incorrecto_es_un_error_que_se_entiende():
    c = cliente(problema(401, "MFA_CODIGO_INVALIDO", "El código no es correcto."), sesion=False)
    with pytest.raises(api.ErrorServicio) as error:
        servicios.segundo_paso(c, "verify", "T", codigo="000000")
    assert error.value.codigo == "MFA_CODIGO_INVALIDO" and str(error.value) == "El código no es correcto."
    assert not isinstance(error.value, api.SesionCerrada) and c.access is None


def test_la_bitacora_no_guarda_codigos_ni_tokens_de_mfa(caplog):
    c = cliente(Respuesta(200, ejemplo("auth", "mfa_confirmar")), Respuesta(200, SESION_ACTUAL),
                Respuesta(200, PERFIL), sesion=False)
    with caplog.at_level("INFO", logger="epidemia.escritorio"):
        servicios.segundo_paso(c, "confirm", "MFA_TOKEN_SECRETO", codigo="654321")
    for secreto in ("MFA_TOKEN_SECRETO", "654321", "JWT_DE_EJEMPLO", "CODIGO-DE-RESPALDO-1"):
        assert secreto not in caplog.text


def test_el_dispositivo_va_solo_si_el_despliegue_lo_pide(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CARPETA_LOCAL", tmp_path)
    sesion = ejemplo("auth", "iniciar_sesion")
    c = cliente(Respuesta(200, sesion), Respuesta(200, SESION_ACTUAL), Respuesta(200, PERFIL),
                Respuesta(200, sesion), Respuesta(200, SESION_ACTUAL), Respuesta(200, PERFIL), sesion=False)
    monkeypatch.setattr(config, "ENVIAR_DISPOSITIVO", False)
    servicios.abrir_sesion(c, "alex", "x", "cap", "7")
    assert "dispositivo_id" not in cuerpo(c.http.llamadas[0])
    monkeypatch.setattr(config, "ENVIAR_DISPOSITIVO", True)
    servicios.abrir_sesion(c, "alex", "x", "cap", "7")
    enviado = cuerpo(c.http.llamadas[3])
    assert enviado["dispositivo_etiqueta"] == "App de escritorio"
    assert 8 <= len(enviado["dispositivo_id"]) <= 128
    assert servicios.dispositivo() == enviado["dispositivo_id"], "el identificador es estable"


# --- Reporte al bucket (RF-F17) -----------------------------------------------------------------

PDF = b"%PDF-1.4\n% reporte de prueba\n%%EOF\n"


def test_subir_reporte_manda_el_pdf_tal_cual_con_su_huella():
    c = cliente(Respuesta(201, ejemplo("evidencias", "subir_reporte")))
    reporte = servicios.subir_reporte(c, [20, 12, 15, 12], "Cierre contra cuarentena", PDF)
    llamada = c.http.llamadas[0]
    assert llamada["metodo"] == "POST" and llamada["ruta"] == "reports"
    assert llamada["cuerpo"] == PDF
    assert llamada["headers"]["Content-Type"] == "application/pdf"
    assert llamada["headers"]["X-Content-SHA256"] == hashlib.sha256(PDF).hexdigest()
    assert llamada["headers"]["Authorization"] == "Bearer acceso"
    assert llamada["params"] == {"runs": "12,15,20", "title": "Cierre contra cuarentena"}
    assert reporte["id"] == 3 and reporte["run_ids"] == [12, 15, 20]


@pytest.mark.parametrize("ids, contenido, mensaje", [
    ([1, 2], b"<html>", "no es un PDF"),
    ([], PDF, "no tiene corridas"),
    (list(range(1, 102)), PDF, "admite 100"),
])
def test_subir_reporte_no_manda_lo_que_el_servidor_rechazaria(ids, contenido, mensaje):
    c = cliente()
    with pytest.raises(api.ErrorServicio, match=mensaje):
        servicios.subir_reporte(c, ids, "", contenido)
    assert c.http.llamadas == []


def test_url_firmada_y_lista_de_reportes():
    c = cliente(Respuesta(200, ejemplo("evidencias", "url_reporte")),
                Respuesta(200, ejemplo("evidencias", "listar_reportes")))
    url = servicios.url_reporte(c, 3)
    assert url["url"].startswith("https://storage.googleapis.com/") and url["minutes"] == 15
    lista = servicios.reportes(c, [12, 15])
    assert [r["id"] for r in lista] == [3] and lista[0]["run_ids"] == [12, 15, 20]
    assert c.http.llamadas[1]["params"] == {"runs": "12,15"}


def test_reporte_sin_permiso_respeta_el_403():
    c = cliente(problema(403, "PERMISSION_DENIED", "detalle interno"))
    with pytest.raises(api.ErrorServicio) as error:
        servicios.subir_reporte(c, [1, 2], "", PDF)
    assert error.value.status == 403 and str(error.value) == api.MENSAJES[403]


# --- Gestión de datos (D6, D53) -----------------------------------------------------------------

META = {"code": "COVID19_NL_2020", "name": "Casos", "disease": "SARS_COV_2_ANCESTRAL", "region": "19",
        "metric": "casos_confirmados", "period": "semana", "source": "DGE", "license": "Datos abiertos",
        "url": "  ", "cutoff": "2021-10-31", "otro": "no va"}


def test_leer_conjunto_por_extension(tmp_path):
    csv = tmp_path / "serie.CSV"
    csv.write_bytes((config.CONTRATOS / "importacion/ejemplos/entrada_serie.csv").read_bytes())
    contenido, tipo = servicios.leer_conjunto(csv)
    assert tipo == "text/csv" and contenido.startswith(b"# Serie")
    with pytest.raises(api.ErrorServicio, match="CSV, JSON o XML"):
        servicios.leer_conjunto(tmp_path / "serie.txt")
    grande = tmp_path / "grande.json"
    grande.write_bytes(b" " * (config.MAX_CONJUNTO_BYTES + 1))
    with pytest.raises(api.ErrorServicio, match="2 MB"):
        servicios.leer_conjunto(grande)


def test_verificar_calidad_manda_el_archivo_y_los_metadatos():
    c = cliente(Respuesta(200, ejemplo("importacion", "validar_conjunto_invalido")))
    datos = servicios.validar_conjunto(c, b"periodo_inicio,valor\n", "text/csv", META)
    llamada = c.http.llamadas[0]
    assert llamada["ruta"] == "datasets/validate" and llamada["headers"]["Content-Type"] == "text/csv"
    assert llamada["cuerpo"] == b"periodo_inicio,valor\n"
    esperados = {k: v for k, v in META.items() if k not in ("url", "otro")}
    assert llamada["params"] == esperados
    assert datos["valido"] is False and len(datos["fallas"]) == 2 and datos["resumen"] is None


def test_verificar_calidad_valida_trae_resumen_y_lista_vacia():
    c = cliente(Respuesta(200, ejemplo("importacion", "validar_conjunto")))
    datos = servicios.validar_conjunto(c, b"x", "text/csv", META)
    assert datos["valido"] is True and datos["fallas"] == [] and datos["resumen"]["puntos"] == 4


@pytest.mark.parametrize("status, ya_existia", [(201, False), (200, True)])
def test_importar_dice_si_creo_otra_version(status, ya_existia):
    c = cliente(Respuesta(status, ejemplo("importacion", "importar_conjunto")))
    conjunto = servicios.importar_conjunto(c, b"x", "application/json", META)
    assert c.http.llamadas[0]["ruta"] == "datasets"
    assert c.http.llamadas[0]["headers"]["Content-Type"] == "application/json"
    assert (conjunto["code"], conjunto["version"], conjunto["ya_existia"]) == ("COVID19_NL_2020_SINTOMAS", 2,
                                                                             ya_existia)


def test_versiones_y_puntos_del_conjunto():
    c = cliente(Respuesta(200, ejemplo("importacion", "listar_conjuntos")),
                Respuesta(200, ejemplo("importacion", "puntos_conjunto")))
    lista = servicios.conjuntos(c)
    assert [(x["code"], x["version"]) for x in lista] == [("COVID19_NL_2020_SINTOMAS", 2),
                                                          ("COVID19_NL_2020_SINTOMAS", 1)]
    assert lista[1]["resumen"]["total"] == 22259
    puntos = servicios.puntos_conjunto(c, 1)
    assert [p["valor"] for p in puntos] == [7, 38, 40, 18]
    assert c.http.llamadas[1]["ruta"] == "datasets/1/points"


def test_puntos_que_no_cumplen_el_xsd_se_rechazan():
    c = cliente(Respuesta(200, b"<serie_observada><inventado>1</inventado></serie_observada>"))
    with pytest.raises(api.ErrorServicio, match="serie_observada.xsd"):
        servicios.puntos_conjunto(c, 1)


# --- Pantallas ----------------------------------------------------------------------------------

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
    def __init__(self, cliente=None):
        self.cliente = cliente or api.Cliente("http://directorio")
        self.errores = []
        self.acciones = []

    def mostrar_error(self, exc):
        self.errores.append(exc)

    def accion(self, texto):
        self.acciones.append(texto)


def test_dialogo_de_login_pide_y_verifica_el_codigo(qt, monkeypatch):
    app, widgets, esperar = qt
    from frontend_desktop.app.ui.login import DialogoLogin
    llamadas = []
    monkeypatch.setattr(servicios, "captcha", lambda c: {"captcha_id": "cap", "pregunta": "3 + 4"})
    monkeypatch.setattr(servicios, "abrir_sesion",
                        lambda c, *a: {"mfa_requerido": True, "mfa_enrolado": True, "mfa_token": "T"})

    def segundo(c, accion, token, **campos):
        llamadas.append((accion, token, campos))
        if campos.get("codigo") == "000000":
            raise api.ErrorServicio("El código no es correcto.", 401, "MFA_CODIGO_INVALIDO")
        return {"usuario": {}, "codigos_respaldo": []}

    monkeypatch.setattr(servicios, "segundo_paso", segundo)
    dialogo = DialogoLogin(api.Cliente("http://directorio"))
    widgets.append(dialogo)
    esperar(app)
    dialogo.usuario.setText("admin")
    dialogo.password.setText("secreto")
    dialogo.respuesta.setText("7")
    dialogo.iniciar()
    esperar(app)
    assert dialogo.pasos.currentIndex() == 1 and dialogo.password.text() == ""
    assert not dialogo.alta.isVisibleTo(dialogo)
    dialogo.codigo.setText("000000")
    dialogo.enviar_codigo()
    esperar(app)
    assert "no es correcto" in dialogo.mensaje.text() and dialogo.pasos.currentIndex() == 1
    dialogo.codigo.setText("123456")
    dialogo.enviar_codigo()
    esperar(app)
    assert llamadas[-1] == ("verify", "T", {"codigo": "123456"})
    assert dialogo.result() == dialogo.DialogCode.Accepted


def test_dialogo_de_login_vuelve_al_inicio_si_el_reto_vencio(qt, monkeypatch):
    app, widgets, esperar = qt
    from frontend_desktop.app.ui.login import DialogoLogin
    monkeypatch.setattr(servicios, "captcha", lambda c: {"captcha_id": "cap", "pregunta": "3 + 4"})

    def vencido(*_, **__):
        raise api.ErrorServicio("El token de MFA no es válido o venció.", 401, "MFA_TOKEN_INVALIDO")

    monkeypatch.setattr(servicios, "segundo_paso", vencido)
    dialogo = DialogoLogin(api.Cliente("http://directorio"))
    widgets.append(dialogo)
    esperar(app)
    dialogo.mostrar_mfa({"mfa_requerido": True, "mfa_enrolado": False, "mfa_token": "T"})
    assert dialogo.alta.isVisibleTo(dialogo) and not dialogo.verificar.isEnabled()
    dialogo.alta.setText("alta")
    dialogo.enrolar()
    esperar(app)
    assert dialogo.pasos.currentIndex() == 0 and dialogo.mfa_token is None
    assert "venció" in dialogo.mensaje.text()

    def sin_acceso(*_, **__):
        raise api.ErrorServicio("La app de escritorio es para analistas y administradores.", 403)

    monkeypatch.setattr(servicios, "segundo_paso", sin_acceso)
    dialogo.mostrar_mfa({"mfa_requerido": True, "mfa_enrolado": True, "mfa_token": "T2"})
    dialogo.codigo.setText("123456")
    dialogo.enviar_codigo()
    esperar(app)
    assert dialogo.pasos.currentIndex() == 0 and "analistas" in dialogo.mensaje.text()


def test_comparacion_sube_el_reporte_y_abre_su_url(qt, monkeypatch):
    app, widgets, esperar = qt
    from frontend_desktop.app.ui import comparacion as modulo
    from frontend_desktop.tests.test_humo import datos_comparacion
    subidas, abiertas = [], []

    def subir(c, ids, titulo, pdf):
        subidas.append((ids, titulo, pdf[:4]))
        return {"id": 3, "size_bytes": 2048, "sha256": "4b1e7d0c9a2f8e6d"}

    monkeypatch.setattr(servicios, "subir_reporte", subir)
    monkeypatch.setattr(servicios, "url_reporte", lambda c, i: {"url": "https://bucket/reporte-%s.pdf" % i})
    monkeypatch.setattr(modulo.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(modulo.QDesktopServices, "openUrl", lambda url: abiertas.append(url.toString()))

    class VentanaComparacion(Ventana):
        def comparar(self, *_):
            pass

    vista = modulo.VistaComparacion(VentanaComparacion())
    widgets.append(vista)
    assert not vista.b_subir.isEnabled() and not vista.b_url.isEnabled()
    vista._mostrar(datos_comparacion())
    assert vista.b_subir.isEnabled() and not vista.b_url.isEnabled()
    vista.subir_reporte()
    esperar(app)
    assert subidas == [([11, 12, 21, 22], "Comparación: Base · v1, Cierre · v1", b"%PDF")]
    assert vista.b_url.isEnabled()
    vista.abrir_reporte()
    esperar(app)
    assert abiertas == ["https://bucket/reporte-3.pdf"]
    assert any("subió el reporte" in a for a in vista.v.acciones) and not vista.v.errores
    vista._mostrar(datos_comparacion())
    assert not vista.b_url.isEnabled(), "otra comparación no reabre el reporte anterior"


def test_pantalla_de_datos_verifica_importa_y_muestra_versiones(qt, monkeypatch, tmp_path):
    app, widgets, esperar = qt
    from frontend_desktop.app.ui.datos import VistaDatos
    validados, importados = [], []
    lista = xmlio.leer(ejemplo("importacion", "listar_conjuntos"))["conjuntos"]
    monkeypatch.setattr(servicios, "enfermedades", lambda c: [{"code": "SARS_COV_2_ANCESTRAL", "nombre": "COVID-19"}])
    monkeypatch.setattr(servicios, "regiones", lambda c: [{"code": "19039", "nombre": "Monterrey"}])
    monkeypatch.setattr(servicios, "conjuntos", lambda c: lista)
    monkeypatch.setattr(servicios, "puntos_conjunto",
                        lambda c, i: xmlio.leer(ejemplo("importacion", "puntos_conjunto"))["puntos"])

    def validar(c, contenido, tipo, meta):
        validados.append((tipo, meta))
        return xmlio.leer(ejemplo("importacion", "validar_conjunto_invalido"))

    def importar(c, contenido, tipo, meta):
        importados.append(meta["code"])
        return dict(xmlio.leer(ejemplo("importacion", "importar_conjunto")), ya_existia=False)

    monkeypatch.setattr(servicios, "validar_conjunto", validar)
    monkeypatch.setattr(servicios, "importar_conjunto", importar)
    vista = VistaDatos(Ventana())
    widgets.append(vista)
    vista.al_mostrar()
    esperar(app)
    assert vista.tabla.rowCount() == 2 and vista.tabla.item(0, 1).text() == "2"
    assert vista.region.itemData(0) == "19" and vista.enfermedad.currentData() == "SARS_COV_2_ANCESTRAL"
    assert not vista.b_importar.isEnabled()
    vista.tabla.selectRow(1)
    esperar(app)
    assert vista.puntos.rowCount() == 4 and "Datos abiertos" in vista.detalle.text()

    archivo = tmp_path / "serie.csv"
    archivo.write_bytes(b"periodo_inicio,valor\n2020-03-01,7\n")
    vista.usar_archivo(archivo)
    vista.campos["code"].setText("COVID19_NL_2020")
    vista.verificar()
    esperar(app)
    assert validados[0][0] == "text/csv"
    assert validados[0][1]["region"] == "19" and validados[0][1]["metric"] == "casos_confirmados"
    assert "2 fallas" in vista.resultado.text() and "entero no negativo" in vista.resultado.text()
    vista.importar()
    esperar(app)
    assert importados == ["COVID19_NL_2020"] and "Se importó COVID19_NL_2020_SINTOMAS v2" in vista.resultado.text()
    assert not vista.v.errores


def test_pantalla_de_datos_muestra_el_rechazo_del_servidor(qt, monkeypatch, tmp_path):
    app, widgets, esperar = qt
    from frontend_desktop.app.ui.datos import VistaDatos
    monkeypatch.setattr(servicios, "enfermedades", lambda c: [])
    monkeypatch.setattr(servicios, "regiones", lambda c: [])
    monkeypatch.setattr(servicios, "conjuntos", lambda c: [])

    def rechazar(*_):
        raise api.ErrorServicio("Datos inválidos.", 422, "DATOS_INVALIDOS",
                                [{"ruta": "code", "mensaje": "code debe ser MAYÚSCULAS."}])

    monkeypatch.setattr(servicios, "importar_conjunto", rechazar)
    vista = VistaDatos(Ventana())
    widgets.append(vista)
    vista.al_mostrar()
    esperar(app)
    assert "Aún no hay conjuntos" in vista.nota.text()
    archivo = tmp_path / "serie.json"
    archivo.write_bytes(b"[]")
    vista.usar_archivo(archivo)
    vista.importar()
    esperar(app)
    assert "rechazó la serie" in vista.resultado.text() and "MAYÚSCULAS" in vista.resultado.text()
    assert not vista.v.errores and vista.b_importar.isEnabled()
