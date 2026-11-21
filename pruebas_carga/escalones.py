"""Forma de carga por escalones, para encontrar la saturación y medir la recuperación (F4).

Se suma a los perfiles: `locust -f pruebas_carga/perfiles.py,pruebas_carga/escalones.py ...`.

    usuarios
      MAX ┤                    ┌──┐
          ┤               ┌────┘  │
          ┤          ┌────┘       │
          ┤     ┌────┘            │
     PASO ┤─────┘                 └──────────── BASE (recuperación)
          └──────────────────────────────────────▶ tiempo
            SEGUNDOS_PASO cada escalón          SEGUNDOS_RECUPERACION

Variables (con su valor por omisión): USUARIOS_PASO (10), SEGUNDOS_PASO (60), USUARIOS_MAX
(100), USUARIOS_BASE (= USUARIOS_PASO) y SEGUNDOS_RECUPERACION (120). analiza.py lee los mismos
valores para separar los escalones.
"""
import os

try:
    from locust import LoadTestShape
except ImportError:  # analiza.py importa ajustes() sin tener Locust instalado
    LoadTestShape = object


def ajustes(entorno=None):
    entorno = os.environ if entorno is None else entorno
    paso = int(entorno.get("USUARIOS_PASO", "10"))
    return {"paso": paso, "segundos_paso": int(entorno.get("SEGUNDOS_PASO", "60")),
            "maximo": int(entorno.get("USUARIOS_MAX", "100")),
            "base": int(entorno.get("USUARIOS_BASE", str(paso))),
            "recuperacion": int(entorno.get("SEGUNDOS_RECUPERACION", "120"))}


def usuarios_en(t, a):
    """Cuántos usuarios hay en el segundo t de la prueba, o None si ya terminó."""
    escalones = max(1, a["maximo"] // a["paso"])
    subida = escalones * a["segundos_paso"]
    if t < subida:
        return a["paso"] * (int(t // a["segundos_paso"]) + 1)
    if t < subida + a["recuperacion"]:
        return a["base"]
    return None


class Escalones(LoadTestShape):
    def __init__(self):
        super().__init__()
        self.a = ajustes()

    def tick(self):
        t = self.get_run_time()
        usuarios = usuarios_en(t, self.a)
        if usuarios is None:
            return None
        # Cada escalón llega en unos 5 s. Al bajar, los usuarios de más se detienen casi de golpe,
        # para que la recuperación empiece en un momento claro.
        subiendo = t < max(1, self.a["maximo"] // self.a["paso"]) * self.a["segundos_paso"]
        return usuarios, max(2, self.a["paso"] / 5) if subiendo else 1000
