# Demostración de fallos (N5), 2026-11-16

Se detuvo o pausó un contenedor del compose de `infra/`, se llamó a las rutas y se comprobó qué respondía el sistema y que volvía solo al restaurar el contenedor. Lo corrió `python infra/demo_fallos.py` (todos los escenarios, sin errores); la salida completa está en [`consola.txt`](consola.txt).

**Aviso.** MongoDB y el bucket todavía no son parte del compose principal (bloque D). Para esta demostración se agregaron con [`infra/docker-compose.fallos.yml`](../../../../infra/docker-compose.fallos.yml): un MongoDB y un emulador del bucket (`fake-gcs-server`), declarados en `resultados` (MongoDB) y `evidencias` (bucket). Esos dos servicios solo revisan la salud de esas dependencias; todavía no guardan nada en ellas. Por eso en estos dos casos se comprueba el `/health` y el panel, no la lógica de reintento de la corrida ni de la subida de archivos (eso falta, bloque D).

## Resultados

| Caso | Cómo se provocó | Qué se esperaba | Qué pasó | Resultado | Evidencia |
|---|---|---|---|---|---|
| Servicio caído | `stop casos` | `casos` no responde; `regiones` sigue en 200; el panel marca `casos` caído; al volver, misma sesión en 200 | `casos` sin conexión, `regiones` 200, panel `caido`; al volver, 200 y panel `ok` | OK | [servicio.txt](evidencia/servicio.txt) |
| Redis caído (servicios) | `stop redis` | Ruta protegida 503 `SERVICIO_NO_DISPONIBLE`; ruta pública 200; recupera sin reiniciar servicios | 503 `SERVICIO_NO_DISPONIBLE` en `casos`; `regiones` 200; al volver Redis, la misma sesión da 200 | OK | [redis.txt](evidencia/redis.txt) |
| Redis caído (web, D33) | `stop redis` con la web corriendo | Sesión ya abierta sigue; entrar de nuevo da 503 con mensaje amable | `/dashboard` con sesión abierta 200; `POST /login` 503 con «El servicio de sesiones no está disponible por ahora…»; al volver, se puede entrar | OK | [redis.txt](evidencia/redis.txt), [log_web_redis.txt](evidencia/log_web_redis.txt) |
| MongoDB caído | `stop mongodb` | `/health` de `resultados` 503 degradado con `mongodb: false`; el panel lista `mongodb` en causas; los demás siguen | Exactamente eso; `regiones` 200; al volver, `/health` 200 y panel `ok` | OK (solo salud) | [mongodb.txt](evidencia/mongodb.txt) |
| PostgreSQL caído | `stop postgres` | `/health` 503; la lectura da 503 `SERVICIO_NO_DISPONIBLE`; recupera al volver | `/health` 503 `postgresql: false`; `GET /cases` 503 `SERVICIO_NO_DISPONIBLE` («La base de datos no está disponible.»); al volver, todo 200 | OK (ver abajo: la primera corrida dio 500 y se corrigió) | [postgres.txt](evidencia/postgres.txt), [log_casos_postgres.txt](evidencia/log_casos_postgres.txt) |
| Bucket caído | `stop bucket` | `/health` de `evidencias` 503 degradado con `bucket: false`; el panel lista `bucket`; los demás siguen | Exactamente eso; al volver, `ok` | OK (solo salud) | [bucket.txt](evidencia/bucket.txt) |
| Tiempo excedido | `pause validacion` y `POST /scenarios` | `escenarios` corta a los ~5 s con 503 `SERVICIO_NO_DISPONIBLE` | 503 `SERVICIO_NO_DISPONIBLE` en 5.0 s; al reanudar, vuelve a responder | OK | [timeout.txt](evidencia/timeout.txt), [log_escenarios_timeout.txt](evidencia/log_escenarios_timeout.txt) |
| Cierre de sesión en la web (I3) | `GET /logout` y reusar la cookie copiada antes | La cookie ya no sirve | `/dashboard` con la cookie copiada: 302 a `/login?next=/dashboard` | OK | [web.txt](evidencia/web.txt) |

## Diferencias y límites

- **PostgreSQL caído: de 500 a 503.** En la primera corrida el servicio respondía `500 ERROR_INTERNO` porque el manejador genérico de `epidemia_comun/fabrica.py` no distinguía `psycopg2.OperationalError`. Se corrigió: los errores de conexión (`OperationalError` sin código SQL o clase `08`/`57P`, e `InterfaceError`) responden `503 SERVICIO_NO_DISPONIBLE` con `Retry-After: 5`, se anotan como aviso sin detalles y cuentan en `errors:<servicio>`; integridad, sintaxis, deadlock y cancelación siguen en 500. Se reconstruyeron los contenedores y se repitió `python infra/demo_fallos.py postgres` (`evidencia/postgres.txt` y `log_casos_postgres.txt` son de la segunda corrida; `consola.txt` solo en su sección de PostgreSQL).
- **MongoDB y bucket: solo se prueba la salud.** Falta demostrar que la corrida termina con su resumen en PostgreSQL sin MongoDB, y que la subida responde 503 sin bucket y el caso no se pierde. Eso depende del bloque D.
- La web con PostgreSQL caído se cubre con una prueba automática (`frontend_web/tests/test_postgres_caido.py`: 503 con la página «El sistema no está disponible por ahora»); no se repitió a mano con la web arrancada.
- Se encontró y corrigió un error del propio guion: el escenario `timeout` usaba la primera enfermedad del catálogo (Dengue), que hoy no es simulable por falta de fuentes en sus parámetros (regla 8), y recibía 422 en vez de llegar al tiempo de espera. Ahora elige una enfermedad con todos sus parámetros respaldados.

## Cómo repetirla

1. Levanta el compose con el archivo de la demostración (sin el perfil `gpu`, que no compila en Mac arm64):
   `docker compose -f infra/docker-compose.yml -f infra/docker-compose.fallos.yml --profile '*' up -d --wait --no-build <servicios>` (o, en una máquina con soporte de GPU, sin la lista de servicios).
2. Opcional, para la parte de la web: arranca `python -m frontend_web.run` con `DATABASE_URL` hacia PostgreSQL (puerto 5433), `REDIS_URL` hacia Redis (puerto 6380) y el mismo `JWT_SECRET_KEY` del compose; define `DEMO_WEB_URL=http://127.0.0.1:5000` (o el puerto que uses).
3. Desde la raíz, con el entorno de Python activo:
   `DEMO_COMPOSE_FILES=infra/docker-compose.yml,infra/docker-compose.fallos.yml DEMO_PASSWORD=<contraseña de admin> python infra/demo_fallos.py`
   (sin `DEMO_PASSWORD` la pide). Para uno solo: `python infra/demo_fallos.py redis`. Escenarios: `servicio`, `redis`, `mongodb`, `postgres`, `bucket`, `timeout`, `web`.
4. Los archivos de `evidencia/` salieron de las mismas llamadas, guardadas antes, durante y después de cada caída.
