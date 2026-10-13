from pathlib import Path

from epidemia_comun.fabrica import crear_app
from .rutas import registrar

# La carpeta usa guion bajo porque Python no importa paquetes con guion; el
# nombre del servicio y su contrato son los del catálogo.
CONTRATO = Path(__file__).resolve().parents[2] / "docs/contratos/tipos-intervencion/openapi.json"

app = crear_app("tipos-intervencion", CONTRATO, registrar)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5215)
