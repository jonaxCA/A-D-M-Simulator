from pathlib import Path

from epidemia_comun.fabrica import crear_app
from .rutas import registrar

CONTRATO = Path(__file__).resolve().parents[2] / "docs/contratos/estado-servicios/openapi.json"

app = crear_app("estado-servicios", CONTRATO, registrar)


if __name__ == "__main__":
    # Solo las rutas; el sondeo arranca con `python -m microservicios.estado_servicios`.
    app.run(host="127.0.0.1", port=5262)
