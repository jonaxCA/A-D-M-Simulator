# EPIDEMIA - Servicio estado-servicios

Directorio de los 27 servicios y sondeo de su salud. No hay pasarela (D13): las apps y
la consola le piden aquí la URL de cada servicio. Cada pocos segundos sondea el
`/health` de los 27, incluido el suyo, **en XML**, y guarda en Redis el último estado
y un historial corto. No lee ni escribe tablas.

Puerto externo: 5262; puerto interno en Docker: 8000. Contrato en
`docs/contratos/estado-servicios/openapi.json`.

## Rutas

Las tres son públicas: hay que saber la URL de `auth` antes de iniciar sesión, y la
salud de cada servicio ya es pública en su `/health`.

| Método | Ruta                               | Qué regresa |
|--------|------------------------------------|-------------|
| GET    | `/api/v1/services`                 | Por servicio: `nombre`, `dominio` (su perfil del compose), `puerto`, `url`, `docs`, `openapi` y la `version` del último sondeo. No sondea |
| GET    | `/api/v1/services/health`          | `resumen` (cuántos `ok`, `degradado` y `caido`) y el último sondeo de cada uno |
| GET    | `/api/v1/services/{nombre}/history`| Sus últimos 30 sondeos, del más reciente al más viejo |

Cada sondeo trae `estado`, `causas`, `detalle`, `version`, `latencia_ms` y `revisado`
(ISO 8601, UTC):

| `estado`    | Cuándo | `causas` | `detalle` |
|-------------|--------|----------|-----------|
| `ok`        | `/health` respondió 200 | `[]` | `null` |
| `degradado` | Respondió 503: el proceso vive, pero le falla la base o Redis | `postgresql`, `redis` o las dos | `null` |
| `caido`     | No respondió, o lo que respondió no es su salud | `proceso` | `sin_conexion`, `tiempo_agotado` o `respuesta_invalida` |

`respuesta_invalida` es una página de error o la salud de otro servicio: el puerto
del directorio no es el de ese servicio. Un servicio detenido sale `caido` con
`sin_conexion`, sin estorbar a los demás.

Errores: un `nombre` que no está en el directorio es 404 `NO_ENCONTRADO`; el historial
con Redis caído es 503 `SERVICIO_NO_DISPONIBLE`.

## Sondeo y Redis

- Un hilo sondea a los 27 a la vez cada `SONDEO_SEGUNDOS` (10 por defecto), con 5 s
  de espera cada uno: en Docker Desktop, el nombre de un contenedor detenido tarda unos
  4 s en no resolverse, así que con Redis caído cada `/health` tarda eso en responder
  503, y con menos espera saldría `caido` en vez de `degradado`.
- El sondeo arranca con `python -m microservicios.estado_servicios`, el `CMD` del
  contenedor, igual que el trabajador de `simulador`. Importar la app no lo prende,
  así que las pruebas no lo ven.
- `health:<servicio>` guarda el último sondeo, y vence a los tres intervalos (30 s):
  si el hilo se detiene, la salud no se queda congelada en verde.
- `health:history:<servicio>` guarda los últimos 30 sondeos, unos 5 minutos. Se
  borra una hora después del último sondeo.
- `/services/health` sondea en ese momento lo que no encuentra en Redis: si venció,
  si Redis está caído o si el hilo no ha corrido. Por eso responde aunque Redis
  esté caído; en ese caso cada consulta sondea a los 27 y tarda unos 8 s (los 4 s
  de no encontrar a Redis, más el sondeo).

Los 27 están en `SERVICIOS` de `sondeo.py`, con su perfil y su puerto. Una prueba
revisa que coincidan con el catálogo y con el compose. Un servicio nuevo del
catálogo se agrega ahí.

## Variables

`DATABASE_URL` (para su `/health`), `JWT_SECRET_KEY` y `REDIS_URL`, como todos.
Además:

| Variable          | Por defecto                 | Qué es |
|-------------------|-----------------------------|--------|
| `URL_PUBLICA`     | `http://{host}:{puerto}`    | La URL que da el directorio a las apps y a la consola |
| `URL_SONDEO`      | `http://127.0.0.1:{puerto}` | Dónde sondea; en el compose, `http://{servicio}:8000` |
| `SONDEO_SEGUNDOS` | `10`                        | Cada cuánto sondea |

En las dos URL, `{puerto}` se cambia por el puerto de cada servicio y `{servicio}`
por su nombre.

Sin `URL_PUBLICA`, el directorio arma cada URL con el host al que llegó la petición:
la consola en `localhost` recibe `http://localhost:5201`, el emulador de Android (que ve la
PC como `10.0.2.2`) recibe `http://10.0.2.2:5201` y un celular en la misma red recibe la IP
de la PC. Un host que no es un nombre ni una IP se cambia por `localhost`. Con
`URL_PUBLICA` fijada, manda ella: sirve si las apps entran por otra dirección.

Su rol de PostgreSQL, `svc_estado_servicios` (migración 030), solo puede conectarse.

## Probarlo

```bash
python -m pytest microservicios/estado_servicios
python -m microservicios.estado_servicios 127.0.0.1:5262
curl "http://127.0.0.1:5262/api/v1/services/health?format=json"
curl "http://127.0.0.1:5262/api/v1/services/zonas/history?format=json"
```

Fuera de Docker sondea `127.0.0.1` en el puerto de cada servicio, así que ve a los
que estén corriendo en tu máquina.
