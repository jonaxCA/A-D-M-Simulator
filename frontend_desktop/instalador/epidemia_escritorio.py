"""Arranque de la app de escritorio empaquetada con PyInstaller (instalador/epidemia_escritorio.spec).

Igual que `python -m frontend_desktop.run`, pero apunta a la nube por omisión: quien instala el .exe
no tiene que fijar variables. Las de siempre (EPIDEMIA_DIRECTORIO, EPIDEMIA_DISPOSITIVO...) siguen
mandando si vienen definidas.

    EPIDEMIA-Escritorio.exe                      abre la app
    EPIDEMIA-Escritorio.exe --verificar <archivo>  revisa el paquete (XSD y estilo) y escribe el resultado
"""
import os
import sys

os.environ.setdefault("EPIDEMIA_DIRECTORIO", "https://epidemos.app/estado-servicios")
os.environ.setdefault("EPIDEMIA_DISPOSITIVO", "1")


def verificar(archivo):
    """Sin pantalla: que el paquete traiga cada XSD (y que cargue) y la hoja de estilos."""
    from pathlib import Path

    from frontend_desktop.app import config, esquemas

    lineas, bien = [], True
    xsds = sorted(config.CONTRATOS.rglob("*.xsd"))
    for xsd in xsds:
        try:
            esquemas.esquema(str(xsd.relative_to(config.CONTRATOS)))
        except Exception as exc:  # noqa: BLE001 - se reporta cualquier falla de carga
            bien = False
            lineas.append("error %s: %s" % (xsd.name, exc))
    estilo = Path(sys.modules["frontend_desktop.run"].__file__).parent / "app" / "ui" / "estilo.qss"
    if not estilo.exists():
        bien = False
        lineas.append("falta estilo.qss")
    lineas.insert(0, "%s: %d XSD cargados, estilo %s, directorio %s" % (
        "ok" if bien and xsds else "error", len(xsds), "sí" if estilo.exists() else "no", config.DIRECTORIO))
    Path(archivo).write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return 0 if bien and xsds else 1


if __name__ == "__main__":
    from frontend_desktop import run

    if len(sys.argv) == 3 and sys.argv[1] == "--verificar":
        sys.exit(verificar(sys.argv[2]))
    sys.exit(run.main())
