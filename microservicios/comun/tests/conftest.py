# pytest toma microservicios/comun como raíz (por su pyproject.toml) y no carga
# microservicios/conftest.py; sin esto, `pytest microservicios/comun/tests` no
# tiene crear_cliente, redis_falso ni token.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from microservicios.conftest import *  # noqa: E402,F401,F403
