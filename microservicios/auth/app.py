from pathlib import Path

from epidemia_comun.fabrica import crear_app
from .rutas import registrar

CONTRATO = Path(__file__).resolve().parents[2] / "docs/contratos/auth/openapi.json"

app = crear_app("auth", CONTRATO, registrar)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5201)
