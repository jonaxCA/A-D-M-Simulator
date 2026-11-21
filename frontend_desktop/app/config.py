import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

DIRECTORIO = os.environ.get("EPIDEMIA_DIRECTORIO", "http://localhost:5262").rstrip("/")
CONTRATOS = Path(os.environ.get("EPIDEMIA_CONTRATOS", RAIZ / "docs" / "contratos"))
TIEMPO_ESPERA = float(os.environ.get("EPIDEMIA_TIEMPO_ESPERA", "15"))

ROLES_PERMITIDOS = ("ANALISTA", "ADMINISTRADOR")
# Los motores implementados (D2). corridas rechaza con 422 uno que el despliegue no tenga en
# MOTORES_HABILITADOS; el compose trae el simulador de abm-ref.
MOTORES = ("seir-ref", "abm-ref")
REPLICAS_DEFECTO = 30
REPLICAS_MAX = 100
LIMITE_COMPARACION = 50

SEGUNDOS_SALUD = 30
SEGUNDOS_SESION = 60
SEGUNDOS_COLA = 3
SEGUNDOS_AVISOS = 60
