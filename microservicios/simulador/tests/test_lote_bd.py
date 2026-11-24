"""El lote sigue a su corrida (065): el trigger reemplaza las copias de _sincroniza_lote que llevaban
corridas y simulador (E8, D37). Cada paso usa la función de verdad de su servicio."""
import pytest

from epidemia_comun.bd import query
from microservicios.corridas import datos as corridas
from microservicios.pruebas_bd import contexto_de_prueba, escribe, tiene_base
from microservicios.simulador import datos as simulador

pytestmark = pytest.mark.skipif(not tiene_base(), reason="Requiere la base de pruebas")


@pytest.fixture
def corrida():
    fila = query("SELECT id FROM scenario_versions WHERE status = 'aprobado' ORDER BY id LIMIT 1", one=True)
    if fila is None:
        pytest.skip("Falta una versión aprobada")
    user_id = query("SELECT min(id) AS id FROM users", one=True)["id"]
    run_id, batch_id, error = corridas.crear_corrida(fila["id"], 424242, user_id, "seir-ref-0.1",
                                                     contexto=contexto_de_prueba(user_id))
    assert error is None
    yield {"run": run_id, "lote": batch_id, "contexto": contexto_de_prueba(user_id)}
    escribe("DELETE FROM simulation_runs WHERE id = %s", (run_id,))
    escribe("DELETE FROM simulation_batches WHERE id = %s", (batch_id,))


def _lote(batch_id):
    return query("SELECT status, finished_at FROM simulation_batches WHERE id = %s", (batch_id,), one=True)


def test_el_lote_sigue_cada_estado_de_su_corrida(corrida):
    assert _lote(corrida["lote"])["status"] == "encolado"
    assert simulador.marcar_run_ejecutando(corrida["run"])
    assert _lote(corrida["lote"]) == {"status": "ejecutando", "finished_at": None}
    assert simulador.marcar_run_fallido(corrida["run"], "Prueba del trigger")
    fallido = _lote(corrida["lote"])
    assert fallido["status"] == "fallido" and fallido["finished_at"] is not None
    assert corridas.reintentar_run(corrida["run"], contexto=corrida["contexto"]) == "normal"
    assert _lote(corrida["lote"]) == {"status": "encolado", "finished_at": None}
    assert corridas.cancelar_run(corrida["run"], contexto=corrida["contexto"])
    cancelado = _lote(corrida["lote"])
    assert cancelado["status"] == "cancelado" and cancelado["finished_at"] is not None


def test_completar_y_reencolar_tambien_mueven_el_lote(corrida):
    simulador.marcar_run_ejecutando(corrida["run"])
    assert [f["id"] for f in simulador.reencola_corridas_interrumpidas("seir-ref", "seir-ref-0.1")] \
        == [corrida["run"]]
    assert _lote(corrida["lote"])["status"] == "encolado"
    simulador.marcar_run_ejecutando(corrida["run"])
    assert simulador.guardar_resultado_run(corrida["run"], {
        "engine_version": "seir-ref-0.1", "huella_escenario": "0" * 64, "resumen": {},
        "trazabilidad_parametros": []})
    completado = _lote(corrida["lote"])
    assert completado["status"] == "completado" and completado["finished_at"] is not None
