from pathlib import Path

from epidemia_comun.fabrica import crear_app
from .rutas import registrar

CONTRATO = Path(__file__).resolve().parents[2] / "docs/contratos/calibracion/openapi.json"

app = crear_app("calibracion", CONTRATO, registrar)


if __name__ == "__main__":
    # Solo la API; el trabajador arranca con CALIBRACION_TRABAJADOR=1 python -m microservicios.calibracion.
    app.run(host="127.0.0.1", port=5246)
