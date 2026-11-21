import pytest

from microservicios.pruebas_bd import contexto_de_prueba, escribe, id_de_usuario, tiene_base
from epidemia_comun.bd import query
from microservicios.auth import mfa

pytestmark = pytest.mark.skipif(not tiene_base(), reason="Requiere la base de pruebas")


@pytest.fixture
def usuario():
    uid = id_de_usuario("diana.flores")
    limpiar = lambda: (escribe("DELETE FROM mfa_backup_codes WHERE user_id = %s", (uid,)),
                       escribe("DELETE FROM user_mfa WHERE user_id = %s", (uid,)))
    limpiar()
    yield uid
    limpiar()


def test_enrolamiento_completo(usuario):
    ctx = contexto_de_prueba(usuario)
    assert mfa.estado(usuario) is None
    secreto = mfa.nuevo_secreto()
    assert mfa.guardar_secreto(ctx, usuario, secreto) is True
    fila = mfa.estado(usuario)
    assert (fila["secret"], fila["enabled"], fila["pendiente_reciente"]) == (secreto, False, True)
    # Un pendiente reciente no se sobrescribe.
    assert mfa.guardar_secreto(ctx, usuario, mfa.nuevo_secreto()) is False
    assert mfa.estado(usuario)["secret"] == secreto
    assert query("SELECT count(*) AS n FROM audit_log WHERE entity_type = 'user_mfa' "
                 "AND entity_id = %s AND action = 'UPDATE'", (str(usuario),), one=True)["n"] >= 1
    codigos = mfa.confirmar(ctx, usuario, 100)
    assert len(codigos) == mfa.RESPALDOS and mfa.confirmar(ctx, usuario, 101) is None
    assert all(len(c.replace("-", "")) == mfa.LARGO_RESPALDO for c in codigos)
    assert mfa.estado(usuario)["enabled"] is True
    # Con MFA activo ya no se cambia el secreto.
    assert mfa.guardar_secreto(ctx, usuario, mfa.nuevo_secreto()) is False
    assert mfa.estado(usuario)["secret"] == secreto
    assert query("SELECT count(*) AS n FROM mfa_backup_codes WHERE user_id = %s",
                 (usuario,), one=True)["n"] == mfa.RESPALDOS


def test_pendiente_vencido_si_se_reemplaza(usuario, monkeypatch):
    ctx = contexto_de_prueba(usuario)
    mfa.guardar_secreto(ctx, usuario, mfa.nuevo_secreto())
    monkeypatch.setattr(mfa, "PENDIENTE_MINUTOS", 0)
    assert mfa.estado(usuario)["pendiente_reciente"] is False
    nuevo = mfa.nuevo_secreto()
    assert mfa.guardar_secreto(ctx, usuario, nuevo) is True and mfa.estado(usuario)["secret"] == nuevo


def test_respaldos_con_sal_por_cuenta(usuario):
    assert mfa._huella(1, "abcde") != mfa._huella(2, "abcde") and len(mfa._huella(1, "abcde")) == 64


def test_un_paso_solo_se_acepta_una_vez(usuario):
    mfa.guardar_secreto(contexto_de_prueba(usuario), usuario, mfa.nuevo_secreto())
    mfa.confirmar(contexto_de_prueba(usuario), usuario, 100)
    assert mfa.aceptar_paso(usuario, 101) is True
    assert mfa.aceptar_paso(usuario, 101) is False and mfa.aceptar_paso(usuario, 100) is False


def test_respaldo_de_un_solo_uso_y_restablecer(usuario):
    ctx = contexto_de_prueba(usuario)
    mfa.guardar_secreto(contexto_de_prueba(usuario), usuario, mfa.nuevo_secreto())
    codigo = mfa.normalizar_respaldo(mfa.confirmar(ctx, usuario, 100)[0].upper())
    assert mfa.usar_respaldo(ctx, usuario, codigo) is True
    assert mfa.usar_respaldo(ctx, usuario, codigo) is False
    assert mfa.usar_respaldo(ctx, usuario, "0" * mfa.LARGO_RESPALDO) is False
    assert mfa.restablecer(ctx, usuario) is True and mfa.estado(usuario) is None
    assert mfa.restablecer(ctx, usuario) is False
    assert not query("SELECT 1 FROM mfa_backup_codes WHERE user_id = %s", (usuario,))
