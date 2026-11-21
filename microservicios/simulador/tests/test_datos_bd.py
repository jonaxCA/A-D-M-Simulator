import pytest

from epidemia_comun.bd import query
from microservicios.pareto import datos as datos_pareto
from microservicios.pareto import dominio
from microservicios.pruebas_bd import tiene_base
from microservicios.simulador import datos, ejecucion

pytestmark = pytest.mark.skipif(not tiene_base(), reason="Requiere la base de pruebas")


def _aprobada():
    fila = query("SELECT id FROM scenario_versions WHERE status = 'aprobado' ORDER BY id LIMIT 1", one=True)
    if fila is None:
        pytest.skip("Falta una versión aprobada")
    return fila["id"]


def test_la_entrada_del_motor_sale_de_la_base_y_el_motor_la_acepta():
    escenario, version, errores = ejecucion.escenario_de_version(_aprobada())
    assert errores == [] and version["status"] == "aprobado"
    from procesamiento.motor import validar_escenario
    assert validar_escenario(escenario) == []


def test_simulador_y_pareto_arman_la_misma_entrada():
    version_id = _aprobada()
    assert dominio.construir_escenario_desde_version(version_id)[0] == \
        ejecucion.escenario_de_version(version_id)[0]


def test_una_version_inexistente():
    assert ejecucion.escenario_de_version(-1) == (None, None, ["La version de escenario no existe."])
    assert datos.version_para_motor(-1) == (None, [])


def test_la_region_de_una_version_y_de_sus_corridas():
    version_id = _aprobada()
    region = datos_pareto.region_de_version(version_id)
    assert isinstance(region, int)
    corridas = [f["id"] for f in query("SELECT id FROM simulation_runs WHERE scenario_version_id = %s",
                                       (version_id,))]
    if corridas:
        assert datos_pareto.regiones_de_corridas(corridas) == {region}
    assert datos_pareto.regiones_de_corridas([]) == set()
