"""abm-gpu atendido por un simulador fuera del compose (D23): el de una PC con GPU que se
conecta a las bases por un túnel (infra/docker-compose.gpu-remoto.yml).

Solo corre con python infra/pruebas_integracion.py --gpu-remoto: el compose de pruebas hace de
máquina de la nube, sin simulador-gpu, y el simulador remoto corre en otro proyecto de Docker,
conectado por un túnel simulado en los mismos puertos que el de verdad (15433, 16380 y 17018,
en el 127.0.0.1 de la PC). Sin eso, se salta.
"""
import json
import os
import subprocess

import pytest

REMOTO = os.environ.get("EPIDEMIA_PRUEBAS_GPU_REMOTO")
pytestmark = pytest.mark.skipif(not REMOTO, reason="Sin --gpu-remoto: no hay simulador remoto.")


def _salud_del_remoto():
    salida = subprocess.run(["docker", "inspect", "-f", "{{.State.Health.Status}}",
                             "%s-simulador-gpu-1" % REMOTO], capture_output=True, text=True)
    return salida.stdout.strip()


def test_el_simulador_remoto_atiende_las_corridas_de_abm_gpu(api, analista, compose, crea_escenario,
                                                            aprueba, termina):
    assert _salud_del_remoto() == "healthy"
    # En la «nube» no hay simulador de abm-gpu: si la corrida termina, la atendió el remoto.
    assert compose("ps", "--format", "{{.Service}}", "simulador-gpu").split() == []

    escenario, version, _ = crea_escenario("GPU remoto")
    aprueba(escenario)
    r = api("corridas", "POST", "/api/v1/runs", analista["access"],
            json={"scenario_version_id": version, "seed": 11, "engine": "abm-gpu"})
    assert r.status_code == 202, r.text
    corrida = r.json()["id"]
    # La primera corrida de un tamaño de población compila las funciones de agente.
    assert termina([corrida], limite=300) == {corrida: "completado"}

    detalle = api("corridas", "GET", "/api/v1/runs/%d" % corrida, analista["access"]).json()
    assert (detalle["engine"], detalle["engine_version"]) == ("abm-gpu", "abm-gpu-0.1")
    # La serie llegó a MongoDB por el túnel; el resumen, a PostgreSQL.
    resultado = api("resultados", "GET", "/api/v1/runs/%d/results" % corrida,
                    analista["access"]).json()
    assert resultado["engine_version"] == "abm-gpu-0.1"
    assert len(resultado["serie"]) == 91  # crea_escenario: 90 días, más el día 0
    assert resultado["resumen"]["casos_acumulados"] >= 10

    # Y el aviso de que terminó, por notificaciones.
    avisos = api("notificaciones", "GET", "/api/v1/notifications", analista["access"]).json()
    assert any(a.get("type") == "RUN_FINISHED" and str(corrida) in json.dumps(a)
               for a in avisos["notificaciones"]), avisos
