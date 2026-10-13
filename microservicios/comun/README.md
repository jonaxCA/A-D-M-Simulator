# EPIDEMIA — biblioteca compartida (trabajo inicial)

Implementación inicial de `epidemia_comun` para todos los microservicios.
**No es todavía un despliegue ni una prueba de aceptación completa.**

## Funciones disponibles

- `cargar_ajustes(nombre)`: lee secreto JWT y Redis; se detiene si falta configuración.
- `responder(datos, raiz)` y `leer_cuerpo()`: XML por defecto, JSON con `?format=json`, lectura segura de XML.
- `ErrorAPI` y `respuesta_error`: errores estándar JSON/XML sin revelar trazas.
- `requiere_token(roles=...)` y `solo_servicios`: verifican JWT HS256, audiencia, vencimiento, sesión en Redis y rol.
- `crear_app(nombre, contrato, registrar_rutas)`: Flask con `/health`, `/docs` y `/openapi.json`.

## Instalación dentro del entorno de desarrollo

Desde la raíz del proyecto:

```bash
pip install -r microservicios/comun/requirements.txt
export PYTHONPATH="$PWD/microservicios/comun:$PWD"
python -m pytest microservicios/comun/tests -q
```

Variables necesarias: `JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL`; opcionales: `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_AUDIENCE_INTERNA`.

No subir `.env` ni secretos. `JWT_ISSUER` predeterminado: `epidemia-auth`;
`JWT_AUDIENCE`: `epidemia-api`; audiencia de rutas internas: `epidemia-interno`.

## Pendientes coordinados con el equipo

1. Acordar con el servicio de `auth` exactamente el contenido de `session:<sha256(sid)>` y sus TTL.
2. Integrar la imagen base, los Dockerfiles y el compose con el responsable de Docker.
3. Decidir CORS, nombres XML/XSD, el mecanismo de token interno y propagación a clientes HTTP.
4. Ejecutar pruebas reales contra Redis, PostgreSQL y el contenedor. Sin esa evidencia no debe marcarse completo el bloque A.

## Plantilla de un servicio nuevo

Ejemplo: `python microservicios/comun/scripts/nuevo_servicio.py regiones 5213`.
Se niega a sobrescribir carpetas existentes. Crea `app.py`, `rutas.py`, `README.md`, `Dockerfile`
y `openapi.json`; **no** registra el servicio en el compose, para no invadir el trabajo de
infraestructura de otro integrante. El servicio generado es un esqueleto y no cumple todavía
los endpoints de negocio ni las evidencias obligatorias.
