# D60 - Python 3.12 como versión mínima

Fecha: 2026-11-23 · Estado: Aceptada · Reemplaza la versión de la regla 11 de `AGENTS.md`

## Contexto
La regla 11 pedía que el código corriera en Python 3.9. Viene del primer sprint (#16, #64) y no tiene razón registrada. Hoy nada la necesita:
- Los contenedores usan `python:3.12-slim` (`infra/docker/base.Dockerfile`).
- La VM de GCP es Debian 13, que trae 3.13.
- PySide6, NumPy 2, psycopg2-binary y las demás dependencias tienen ruedas para 3.12 y 3.13.
- En la suite del 2026-11-19 consta Python 3.14.

Mantenerla cuesta: el CI en 3.9 encontró dos fallas que nadie había visto (`int | None` en un dataclass de `backend_web/contexto.py` y `Path.write_text(newline=)` en `datos/scripts/build_camas_censables.py`), y `ubuntu-latest` ya no trae 3.9 en `setup-python`.

## Opciones consideradas
- A) Seguir en 3.9.
- B) 3.12: la de los contenedores y la que traen Ubuntu 24.04 y WSL.
- C) 3.13: la de Debian 13.

## Decisión
B. Es la versión más nueva que ya corre en todas partes donde sabemos que corre el proyecto. C deja fuera a quien use Ubuntu 24.04 o WSL sin instalar otra versión.

- La regla 11 queda en 3.12: se permiten `X | Y` en anotaciones, `match` y lo que agregó la biblioteca estándar hasta 3.12.
- `ruff.toml` usa `target-version = "py312"`; el CI corre las pruebas en 3.12 y 3.13.
- `epidemia-comun` pide `requires-python >= 3.12`; `python epidemia.py doctor` avisa si la versión es menor.
- El código que ya existe no se reescribe: `Optional[...]` sigue siendo válido.

## Consecuencias
- Quien use el Python de fábrica de macOS (3.9) tiene que instalar 3.12 o más para correr el sitio, el escritorio o las pruebas fuera de Docker.
- Los contenedores no cambian.
- Quien tenga una versión menor lo ve con `python epidemia.py doctor`.
