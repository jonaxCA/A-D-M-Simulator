"""abm-gpu de punta a punta (D23): corridas lo encola en su cola, simulador-gpu lo corre en la
GPU y resultados muestra las simplificaciones del motor.

Solo corre si el compose de pruebas se levantó con GPU (python infra/pruebas_integracion.py
--gpu); si no, se salta.
"""
import pytest


def test_una_corrida_de_abm_gpu_la_corre_simulador_gpu(api, analista, compose, crea_escenario,
                                                      aprueba, termina):
    sanos = compose("ps", "--format", "{{.Service}} {{.Health}}", "simulador-gpu").split()
    if not sanos:
        pytest.skip("simulador-gpu no está arriba: el compose de pruebas se levantó sin --gpu.")
    assert sanos == ["simulador-gpu", "healthy"]
    escenario, version, _ = crea_escenario("GPU")
    aprueba(escenario)

    def procesadas_del_seir():
        return api("simulador", "GET", "/api/v1/worker/status", analista["access"]).json()["procesadas"]
    antes = procesadas_del_seir()

    r = api("corridas", "POST", "/api/v1/runs", analista["access"],
            json={"scenario_version_id": version, "seed": 7, "engine": "abm-gpu"})
    assert r.status_code == 202, r.text
    corrida = r.json()
    assert corrida["engine"] == "abm-gpu"
    # La primera corrida de un tamaño de población compila las funciones de agente.
    assert termina([corrida["id"]], limite=300) == {corrida["id"]: "completado"}

    detalle = api("corridas", "GET", "/api/v1/runs/%d" % corrida["id"], analista["access"]).json()
    assert (detalle["engine"], detalle["engine_version"]) == ("abm-gpu", "abm-gpu-0.1")
    resultado = api("resultados", "GET", "/api/v1/runs/%d/results" % corrida["id"],
                    analista["access"]).json()
    assert resultado["engine_version"] == "abm-gpu-0.1"
    assert any("FLAME GPU" in s for s in resultado["simplificaciones"])
    assert procesadas_del_seir() == antes
