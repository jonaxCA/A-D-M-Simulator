from pathlib import Path

from epidemia_comun.fabrica import crear_app
from .rutas import registrar

CONTRATO = Path(__file__).resolve().parents[2] / "docs/contratos/simulador/openapi.json"

app = crear_app("simulador", CONTRATO, registrar)


if __name__ == "__main__":
    # Solo la ruta de estado; el trabajador arranca con `python -m microservicios.simulador`.
    app.run(host="127.0.0.1", port=5242)
