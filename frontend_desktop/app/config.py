import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

DIRECTORIO = os.environ.get("EPIDEMIA_DIRECTORIO", "http://localhost:5262").rstrip("/")
CONTRATOS = Path(os.environ.get("EPIDEMIA_CONTRATOS", RAIZ / "docs" / "contratos"))
TIEMPO_ESPERA = float(os.environ.get("EPIDEMIA_TIEMPO_ESPERA", "15"))

ROLES_PERMITIDOS = ("ANALISTA", "ADMINISTRADOR")
# D41: el identificador del equipo se manda solo si el despliegue lo exige (MFA prendido o
# DISPOSITIVO_OBLIGATORIO=1), igual que la web: si no, una cuenta nueva en otro equipo quedaría pendiente.
ENVIAR_DISPOSITIVO = os.environ.get("EPIDEMIA_DISPOSITIVO") == "1"
CARPETA_LOCAL = Path(os.environ.get("EPIDEMIA_CARPETA_LOCAL", Path.home() / ".epidemia-escritorio"))
# Límites que revisa el servidor; aquí solo evitan subir un archivo que de todos modos rechazaría.
MAX_REPORTE_BYTES = 20 * 1024 * 1024
MAX_CORRIDAS_REPORTE = 100
MAX_CONJUNTO_BYTES = 2 * 1024 * 1024
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
