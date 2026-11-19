"""abm-ref de punta a punta (D2, D22): corridas lo encola en su cola, simulador-abm lo corre y
resultados muestra las simplificaciones del ABM.

simulador-abm es el mismo servicio simulador con SIMULADOR_MOTOR=abm-ref, sin puerto publicado:
que lo corrió él se ve en que el simulador del SEIR no procesó nada.
"""


def test_una_corrida_de_abm_ref_la_corre_simulador_abm(api, analista, compose, crea_escenario,
                                                      aprueba, termina):
    sanos = compose("ps", "--format", "{{.Service}} {{.Health}}", "simulador-abm").split()
    assert sanos == ["simulador-abm", "healthy"]
    escenario, version, _ = crea_escenario("ABM")
    aprueba(escenario)

    def procesadas_del_seir():
        return api("simulador", "GET", "/api/v1/worker/status", analista["access"]).json()["procesadas"]
    antes = procesadas_del_seir()

    r = api("corridas", "POST", "/api/v1/runs", analista["access"],
            json={"scenario_version_id": version, "seed": 7, "engine": "abm-ref"})
    assert r.status_code == 202, r.text
    corrida = r.json()
    assert corrida["engine"] == "abm-ref"
    assert termina([corrida["id"]], limite=300) == {corrida["id"]: "completado"}

    detalle = api("corridas", "GET", "/api/v1/runs/%d" % corrida["id"], analista["access"]).json()
    assert (detalle["engine"], detalle["engine_version"]) == ("abm-ref", "abm-ref-0.1")
    resultado = api("resultados", "GET", "/api/v1/runs/%d/results" % corrida["id"],
                    analista["access"]).json()
    assert resultado["engine_version"] == "abm-ref-0.1"
    assert any("hogares" in s for s in resultado["simplificaciones"])
    assert procesadas_del_seir() == antes
