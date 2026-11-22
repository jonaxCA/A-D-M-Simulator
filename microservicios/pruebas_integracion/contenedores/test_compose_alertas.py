"""F7 en los contenedores: estado-servicios cuenta a los simuladores vivos por su latido, y un
servicio caído llega como aviso SYSTEM a los ADMINISTRADOR, igual que su recuperación."""
from .conftest import espera


def _motores(api):
    datos = api("estado-servicios", "GET", "/api/v1/services/capacity").json()
    return {m["nombre"]: m for m in datos["motores"]}


def test_estado_servicios_ve_vivos_a_los_simuladores(api):
    # simulador y simulador-2 (seir-ref) y simulador-abm (abm-ref): cada uno late cada 10 s.
    def vivos():
        motores = _motores(api)
        return motores if motores["seir-ref"]["vivos"] == 2 and motores["abm-ref"]["vivos"] >= 1 else None
    motores = espera(vivos, 40, "estado-servicios no ve vivos a los simuladores")
    seir = motores["seir-ref"]
    assert seir["ocupados"] + seir["libres"] == 2
    assert {s["procesadas"] is not None for s in seir["simuladores"]} == {True}


def test_un_servicio_caido_avisa_a_los_administradores(api, sesion, compose):
    admin = sesion("admin")

    def bandeja():
        return api("notificaciones", "GET", "/api/v1/notifications", admin["access"],
                   params={"limit": 200}).json()["notificaciones"]
    ultimo = max((a["id"] for a in bandeja()), default=0)

    def aviso(titulo):
        return [a for a in bandeja() if a["id"] > ultimo and a["type"] == "SYSTEM" and a["title"] == titulo]

    compose("stop", "zonas")
    try:
        # Hasta 2 min de gracia si estado-servicios acaba de arrancar, más 30 s de confirmación.
        caida = espera(lambda: aviso("zonas está caído"), 240, "No llegó el aviso de zonas caído", cada=5)
    finally:
        compose("start", "zonas")
    assert caida[0]["body"].startswith("zonas: en línea → caído")
    assert caida[0]["payload"]["servicios"][0]["estado"] == "caido"
    espera(lambda: aviso("zonas se recuperó"), 120, "No llegó el aviso de que zonas se recuperó", cada=5)
