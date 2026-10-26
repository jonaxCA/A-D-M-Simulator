"""El flujo completo por HTTP: sesión, escenario, intervenciones, aprobación, corrida, resultados,
comparación y Pareto. También: la misma semilla y la misma versión dan el mismo resultado."""
from .conftest import INTERVENCIONES, espera

FUENTE = "Supuesto de la prueba de integración"


def test_flujo_completo(api, sesion, analista, crea_escenario, aprueba, lanza, termina):
    admin = sesion("admin")
    escenario, version, intervenciones = crea_escenario("Flujo", INTERVENCIONES)
    # pareto no traza la frontera sin el costo de cada intervención (regla 8).
    for intervencion in intervenciones.values():
        r = api("intervenciones", "PUT", "/api/v1/versions/%d/interventions/%d/cost" % (version, intervencion),
                admin["access"], json={"unit_cost": "100", "cost_source": FUENTE, "cost_is_assumption": True})
        assert r.status_code == 200, r.text
    aprueba(escenario)

    def aviso():
        lista = api("notificaciones", "GET", "/api/v1/notifications", analista["access"]).json()["notificaciones"]
        return [n for n in lista if n["type"] == "SCENARIO_APPROVED" and n["payload"].get("scenario_id") == escenario]
    espera(aviso, 10, "La analista no recibió el aviso de aprobación.")

    a, b, c = lanza(version, 11), lanza(version, 11), lanza(version, 12)
    assert termina([a, b, c]) == {a: "completado", b: "completado", c: "completado"}

    resultado = api("resultados", "GET", "/api/v1/runs/%d/results" % a, analista["access"]).json()
    assert resultado["aviso"]
    indicadores = {i: api("resultados", "GET", "/api/v1/runs/%d/indicators" % i, analista["access"]).json()["resumen"]
                   for i in (a, b)}
    assert indicadores[a] == indicadores[b]

    comparacion = api("comparacion", "GET", "/api/v1/comparisons", analista["access"], params={"runs": "%d,%d" % (a, c)})
    assert comparacion.status_code == 200 and [x["id"] for x in comparacion.json()["corridas"]] == [a, c]
    pareto = api("pareto", "GET", "/api/v1/pareto", analista["access"], params={"runs": "%d,%d" % (a, c)})
    assert pareto.status_code == 200, pareto.text
    assert set(pareto.json()["frontera"]) <= {a, c} and pareto.json()["frontera"]
