"""Prepara carpetas y archivos de un microservicio sin sobrescribir trabajo previo."""
import argparse
import json
import re
from pathlib import Path


def crear_archivos(raiz_repo, nombre, puerto):
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", nombre):
        raise ValueError("El nombre debe usar minúsculas, guiones y números.")
    if not 1024 <= puerto <= 65535:
        raise ValueError("El puerto debe estar entre 1024 y 65535.")
    carpeta = raiz_repo / "microservicios" / nombre
    carpeta_contrato = raiz_repo / "docs" / "contratos" / nombre
    if carpeta.exists() or carpeta_contrato.exists():
        raise FileExistsError("El servicio ya existe; no se modificó ningún archivo.")
    carpeta.mkdir(parents=True)
    carpeta_contrato.mkdir(parents=True)
    (carpeta / "__init__.py").write_text("", encoding="utf-8")
    (carpeta / "app.py").write_text(
        "from pathlib import Path\n"
        "from epidemia_comun.fabrica import crear_app\n"
        "from .rutas import registrar\n\n"
        "CONTRATO = Path(__file__).resolve().parents[2] / "
        f"\"docs/contratos/{nombre}/openapi.json\"\n"
        f"app = crear_app(\"{nombre}\", CONTRATO, registrar)\n",
        encoding="utf-8")
    (carpeta / "rutas.py").write_text(
        "def registrar(app):\n    # Agregar aquí solo rutas propias del dominio.\n    pass\n",
        encoding="utf-8")
    (carpeta / "Dockerfile").write_text(
        "FROM epidemia/base\n"
        f"COPY microservicios/{nombre}/ /app/microservicios/{nombre}/\n"
        f"CMD [\"waitress-serve\", \"--listen=0.0.0.0:8000\", \"microservicios.{nombre}.app:app\"]\n",
        encoding="utf-8")
    (carpeta / "README.md").write_text(
        f"# {nombre} — plantilla inicial\n\nPuerto externo previsto: {puerto}; puerto interno: 8000.\n"
        "**Todavía no implementa operaciones de negocio.** Agregar rutas, pruebas y evidencias.\n",
        encoding="utf-8")
    contrato = {"openapi": "3.0.3", "info": {"title": "EPIDEMIA - " + nombre, "version": "0.1.0"},
                "servers": [{"url": "http://localhost:" + str(puerto)}], "paths": {}}
    (carpeta_contrato / "openapi.json").write_text(json.dumps(contrato, indent=2), encoding="utf-8")
    return carpeta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("nombre")
    parser.add_argument("puerto", type=int)
    args = parser.parse_args()
    raiz = Path(__file__).resolve().parents[3]
    carpeta = crear_archivos(raiz, args.nombre, args.puerto)
    print("Creado:", carpeta)
    print("Pendiente: agregar servicio y puerto a infra/docker-compose.yml con el equipo de Docker.")


if __name__ == "__main__":
    main()
