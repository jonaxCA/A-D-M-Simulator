"""La cola: dos simulador y diez corridas; cada corrida se ejecuta una sola vez.

El segundo simulador (simulador-2) sale de infra/docker-compose.pruebas.yml y no publica puerto:
que tomó corridas se ve en que el primero no las ejecutó todas.
"""


def test_dos_simuladores_y_diez_corridas(api, analista, base, compose, crea_escenario, aprueba, lanza, termina):
    sanos = compose("ps", "--format", "{{.Service}} {{.Health}}", "simulador", "simulador-2").split()
    assert sanos == ["simulador", "healthy", "simulador-2", "healthy"]
    escenario, version, _ = crea_escenario("Cola")
    aprueba(escenario)

    def procesadas():
        return api("simulador", "GET", "/api/v1/worker/status", analista["access"]).json()["procesadas"]
    antes = procesadas()
    ids = [lanza(version, semilla) for semilla in range(100, 110)]
    assert set(termina(ids).values()) == {"completado"}

    conexion = base()
    with conexion.cursor() as cur:
        cur.execute("""SELECT entity_id, count(*) FROM audit_log
                       WHERE action = 'RUN' AND entity_id = ANY(%s) AND data_after->>'estado' = 'ejecutando'
                       GROUP BY entity_id""", ([str(i) for i in ids],))
        arranques = dict(cur.fetchall())
        cur.execute("SELECT count(*) FROM simulation_results WHERE run_id = ANY(%s)", (ids,))
        resultados = cur.fetchone()[0]
    conexion.close()
    assert arranques == {str(i): 1 for i in ids}
    assert resultados == len(ids)
    # Si un solo trabajador las hubiera tomado todas, el otro no estaría probado.
    assert 0 < procesadas() - antes < len(ids)
