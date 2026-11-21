import pytest

from microservicios.pruebas_bd import contexto_de_prueba, escribe, id_de_usuario, tiene_base
from epidemia_comun.bd import query
from epidemia_comun import llaves
from microservicios.sesiones import almacen as sesiones
from microservicios.sesiones import dispositivos

pytestmark = pytest.mark.skipif(not tiene_base(), reason="Requiere la base de pruebas")

ID_A, ID_B = "dispositivo-a-0001", "dispositivo-b-0002"


@pytest.fixture
def usuarios():
    admin, otro = id_de_usuario("admin"), id_de_usuario("diana.flores")
    limpiar = lambda: escribe("DELETE FROM session_devices WHERE user_id IN (%s, %s)", (admin, otro))
    limpiar()
    yield admin, otro
    limpiar()


def test_el_primero_nace_autorizado_y_el_segundo_pendiente(usuarios):
    _, otro = usuarios
    primero = dispositivos.registrar(contexto_de_prueba(otro), otro, ID_A, "Laptop")
    segundo = dispositivos.registrar(contexto_de_prueba(otro), otro, ID_B, None)
    assert (primero["status"], primero["authorized_by"]) == ("autorizado", otro)
    assert segundo["status"] == "pendiente" and segundo["authorized_at"] is None
    otra_vez = dispositivos.registrar(contexto_de_prueba(otro), otro, ID_A, "Laptop")
    assert otra_vez["id"] == primero["id"] and len(dispositivos.listar(otro)) == 2
    asi_se_guarda = query("SELECT device_hash FROM session_devices WHERE id = %s",
                          (primero["id"],), one=True)["device_hash"]
    assert asi_se_guarda == llaves.huella(ID_A) and ID_A not in str(primero)


def test_la_persona_autoriza_el_suyo_y_no_el_ajeno(usuarios):
    admin, otro = usuarios
    dispositivos.registrar(contexto_de_prueba(otro), otro, ID_A, None)
    pendiente = dispositivos.registrar(contexto_de_prueba(otro), otro, ID_B, None)
    ficha, error = dispositivos.cambiar(contexto_de_prueba(admin), pendiente["id"], False, "autorizado")
    assert (ficha, error) == (None, "NO_ENCONTRADO")
    ficha, error = dispositivos.cambiar(contexto_de_prueba(otro), pendiente["id"], False, "autorizado")
    assert error is None and ficha["status"] == "autorizado" and ficha["authorized_by"] == otro
    assert dispositivos.cambiar(contexto_de_prueba(otro), pendiente["id"], False, "autorizado")[1] == "SIN_CAMBIO"


def test_revocar_cierra_sus_sesiones_y_solo_admin_lo_reautoriza(usuarios, redis_falso):
    admin, otro = usuarios
    ficha = dispositivos.registrar(contexto_de_prueba(otro), otro, ID_A, None)
    h = llaves.huella(ID_A)
    de_ese = sesiones.abrir(otro, ["ANALISTA"], 600, dispositivo=h)
    de_otro = sesiones.abrir(otro, ["ANALISTA"], 600, dispositivo=llaves.huella(ID_B))
    revocado, error = dispositivos.cambiar(contexto_de_prueba(admin), ficha["id"], True, "revocado",
                                           sesiones.cerrar_dispositivo)
    assert error is None and revocado["status"] == "revocado"
    assert sesiones.obtener(de_ese["sid"]) is None and sesiones.obtener(de_otro["sid"])
    assert dispositivos.cambiar(contexto_de_prueba(otro), ficha["id"], False, "autorizado")[1] == "SOLO_ADMIN"
    assert dispositivos.cambiar(contexto_de_prueba(admin), ficha["id"], True, "autorizado")[0]["status"] == "autorizado"


def test_cada_cambio_queda_en_la_bitacora(usuarios):
    _, otro = usuarios
    ficha = dispositivos.registrar(contexto_de_prueba(otro), otro, ID_A, None)
    dispositivos.cambiar(contexto_de_prueba(otro), ficha["id"], False, "revocado")
    acciones = [f["action"] for f in query(
        "SELECT action FROM audit_log WHERE entity_type = 'session_devices' AND entity_id = %s "
        "ORDER BY id", (str(ficha["id"]),))]
    assert acciones == ["CREATE", "UPDATE"]


def test_autorizado_solo_es_cierto_con_estado_autorizado(usuarios):
    _, otro = usuarios
    dispositivos.registrar(contexto_de_prueba(otro), otro, ID_A, None)
    dispositivos.registrar(contexto_de_prueba(otro), otro, ID_B, None)
    assert dispositivos.autorizado(otro, llaves.huella(ID_A)) is True
    assert dispositivos.autorizado(otro, llaves.huella(ID_B)) is False
    assert dispositivos.autorizado(otro, llaves.huella("nunca-visto-0001")) is False


def test_el_tope_de_pendientes_frena_el_registro(usuarios):
    from epidemia_comun.errores import ErrorAPI
    _, otro = usuarios
    ctx = contexto_de_prueba(otro)
    dispositivos.registrar(ctx, otro, ID_A, None)
    for i in range(dispositivos.MAX_PENDIENTES):
        dispositivos.registrar(ctx, otro, "pendiente-%04d" % i, None)
    with pytest.raises(ErrorAPI) as e:
        dispositivos.registrar(ctx, otro, "pendiente-extra", None)
    assert e.value.estado == 429
    assert dispositivos.registrar(ctx, otro, "pendiente-0000", None)["status"] == "pendiente"


def test_registros_simultaneos_solo_autorizan_uno(usuarios):
    from concurrent.futures import ThreadPoolExecutor
    _, otro = usuarios
    ctx = contexto_de_prueba(otro)
    with ThreadPoolExecutor(6) as pool:
        fichas = list(pool.map(lambda i: dispositivos.registrar(ctx, otro, "carrera-%04d" % i, None),
                               range(6)))
    assert sorted(f["status"] for f in fichas).count("autorizado") == 1
