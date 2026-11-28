import copy
from datetime import date

# r0 lo estima la calibración; ρ (la fracción de contagios que se reporta) nunca entra al motor, y
# φ es la reducción de contactos de la Jornada Nacional de Sana Distancia (D50).
FUENTE_MUESTRA = "Muestra de la calibración (D50)"

# Las tres van sin fin: es supuesto que el cambio de conducta persiste durante la ventana (D50).
JORNADA = (
    {"tipo": "CIERRE_ESCUELAS", "desde": "2020-03-23", "reduccion": 1.0,
     "fuente": "Acuerdo SEP 02/03/20, DOF del 16-03-2020, ampliado al 30-05-2020"},
    {"tipo": "CIERRE_TRABAJO", "desde": "2020-03-30", "reduccion": "phi",
     "fuente": "Acuerdo de Salud, DOF del 21-04-2020: actividades no esenciales del 30-03 al 30-05"},
    {"tipo": "REDUCCION_AFORO", "desde": "2020-03-23", "reduccion": "phi",
     "fuente": "Jornada Nacional de Sana Distancia, desde el 23-03-2020"},
)


def jornada(inicio, dias):
    inicio = date.fromisoformat(str(inicio))
    salida = []
    for iv in JORNADA:
        dia = (date.fromisoformat(iv["desde"]) - inicio).days
        if dia < dias:
            salida.append(dict(iv, dia_inicio=max(0, dia)))
    return salida


def infectados_iniciales(c0, rho):
    return max(1, round(c0 / rho))


def escenario_de_muestra(base, intervenciones, dias, c0, r0, rho, phi):
    enfermedad = copy.deepcopy(base["enfermedad"])
    enfermedad["r0"] = {"valor": float(r0), "fuente": FUENTE_MUESTRA, "supuesto": True}
    escenario = {
        "poblacion": copy.deepcopy(base["poblacion"]),
        "infectados_iniciales": infectados_iniciales(c0, rho),
        "dias": dias,
        "enfermedad": enfermedad,
        "intervenciones": [{
            "tipo": iv["tipo"], "dia_inicio": iv["dia_inicio"], "dia_fin": None,
            "cobertura": 1.0, "cumplimiento": 1.0,
            "params": {"reduccion": float(phi if iv["reduccion"] == "phi" else iv["reduccion"])},
        } for iv in intervenciones],
    }
    if base.get("poblacion_edad_desconocida"):
        escenario["poblacion_edad_desconocida"] = base["poblacion_edad_desconocida"]
        escenario["politica_edad_desconocida"] = base["politica_edad_desconocida"]
    return escenario
