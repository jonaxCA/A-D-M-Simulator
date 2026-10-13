import os
from pathlib import Path

SECRETOS_DE_EJEMPLO = {
    "dev-secret-cambiar-en-despliegue",
    "CAMBIAR_POR_UNA_CADENA_LARGA_Y_ALEATORIA",
    "pon-aqui-cualquier-cadena-larga-y-aleatoria",
}


def cargar_ajustes(nombre, entorno=None):
    if entorno is None:
        # Se cargan primero los archivos de prueba/despliegue. El entorno del
        # proceso siempre tiene prioridad, sin guardar secretos en Git.
        from dotenv import load_dotenv
        raiz = Path(__file__).resolve().parents[3]
        load_dotenv(raiz / ".env.shared", override=False)
        load_dotenv(raiz / "microservicios" / nombre / ".env", override=False)
    entorno = os.environ if entorno is None else entorno
    secreto = (entorno.get("JWT_SECRET_KEY") or "").strip()
    redis_url = (entorno.get("REDIS_URL") or "").strip()
    if not secreto or secreto in SECRETOS_DE_EJEMPLO or secreto.startswith("CAMBIAR_"):
        raise RuntimeError("Configura JWT_SECRET_KEY con un secreto propio antes de iniciar.")
    if not redis_url or "CAMBIAR_" in redis_url:
        raise RuntimeError("Configura REDIS_URL antes de iniciar.")
    return {
        "NOMBRE_SERVICIO": nombre,
        "VERSION_SERVICIO": entorno.get("VERSION_SERVICIO") or "0.1.0",
        "JWT_SECRET_KEY": secreto,
        "JWT_ISSUER": entorno.get("JWT_ISSUER") or "epidemia-auth",
        "JWT_AUDIENCE": entorno.get("JWT_AUDIENCE") or "epidemia-api",
        "JWT_AUDIENCE_INTERNA": entorno.get("JWT_AUDIENCE_INTERNA") or "epidemia-interno",
        "REDIS_URL": redis_url,
        "CONSOLE_ORIGIN": entorno.get("CONSOLE_ORIGIN") or "",
    }
