"""Token de acceso para probar las rutas protegidas desde Swagger o Postman.

SOLO PARA DESARROLLO, mientras no exista el servicio `auth`: abre una sesión
real en Redis con `sesiones.abrir()` y firma un access con los mismos claims
que va a emitir `auth` (iss, aud, sub, roles, sid, jti, iat, nbf, exp).

Necesita las mismas variables que los servicios: JWT_SECRET_KEY y REDIS_URL
(y JWT_ISSUER / JWT_AUDIENCE si no usan los valores por omisión).

    python microservicios/comun/scripts/token_pruebas.py --roles ANALISTA
    python microservicios/comun/scripts/token_pruebas.py --roles EPIDEMIOLOGO ADMINISTRADOR --minutos 60

Imprime solo el token, para poder guardarlo en una variable:

    TOKEN=$(python microservicios/comun/scripts/token_pruebas.py)
"""
import argparse
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")


def emitir(usuario, roles, minutos, ajustes):
    import jwt
    from epidemia_comun import sesiones
    ttl = minutos * 60
    sesion = sesiones.abrir(usuario, roles, ttl=ttl)
    ahora = int(time.time())
    claims = {"iss": ajustes["JWT_ISSUER"], "aud": ajustes["JWT_AUDIENCE"],
              "sub": str(usuario), "roles": list(roles), "sid": sesion["sid"],
              "jti": str(uuid.uuid4()), "iat": ahora, "nbf": ahora, "exp": ahora + ttl}
    return jwt.encode(claims, ajustes["JWT_SECRET_KEY"], algorithm="HS256")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--usuario", type=int, default=1, help="id de users (por omisión 1)")
    parser.add_argument("--roles", nargs="+", choices=ROLES, default=["ANALISTA"])
    parser.add_argument("--minutos", type=int, default=20, help="vida del token y de la sesión")
    args = parser.parse_args()
    if not 1 <= args.minutos <= 480:
        parser.error("--minutos debe estar entre 1 y 480")
    from epidemia_comun.ajustes import cargar_ajustes
    # "comun" no tiene .env propio: lee .env.shared y el entorno, como los servicios.
    ajustes = cargar_ajustes("comun")
    print(emitir(args.usuario, args.roles, args.minutos, ajustes))


if __name__ == "__main__":
    main()
