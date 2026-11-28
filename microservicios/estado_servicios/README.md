# EPIDEMIA - Servicio estado-servicios

Directorio de los 31 servicios y sondeo de su salud. No hay pasarela (D13): las apps y
la consola le piden aquí la URL de cada servicio. Cada pocos segundos sondea el
`/health` de los 31, incluido el suyo, **en XML**. Guarda el último estado en Redis y
cada sondeo en MongoDB (`historial_servicios`, D28), que lo conserva 30 días. No lee ni
escribe tablas. También cuenta, por motor, las corridas en cola y los simuladores vivos y
ocupados, y avisa a los ADMINISTRADOR cuando un servicio cae o se recupera (F7).

Puerto externo: 5262; puerto interno en Docker: 8000. Contrato en
`docs/contratos/estado-servicios/openapi.json`.

## Rutas

Las cuatro son públicas: hay que saber la URL de `auth` antes de iniciar sesión, y la
salud de cada servicio ya es pública en su `/health`.

| Método | Ruta                               | Qué regresa |
|--------|------------------------------------|-------------|
| GET    | `/api/v1/services`                 | Por servicio: `nombre`, `dominio` (su perfil del compose), `puerto`, `url`, `docs`, `openapi` y la `version` del último sondeo. No sondea |
| GET    | `/api/v1/services/health`          | `resumen` (cuántos `ok`, `degradado` y `caido`) y el último sondeo de cada uno |
| GET    | `/api/v1/services/capacity`        | Por motor (`seir-ref`, `abm-ref`, `abm-gpu`): `en_cola` y `en_cola_por_prioridad` (`alta`, `normal`, `baja`, D44), `vivos`, `ocupados`, `libres` y cada simulador con su `corrida_actual`, `procesadas` y `visto`. Ver «Colas y capacidad» |
| GET    | `/api/v1/services/{nombre}/history`| Sus últimos 30 sondeos, del más reciente al más viejo, y `resumen` de las últimas 24 h: `sondeos`, `disponibilidad` (fracción en `ok`) y `latencia_promedio_ms` (RF-K03) |

Cada sondeo trae `estado`, `causas`, `detalle`, `version`, `latencia_ms` y `revisado`
(ISO 8601, UTC):

| `estado`    | Cuándo | `causas` | `detalle` |
|-------------|--------|----------|-----------|
| `ok`        | `/health` respondió 200 | `[]` | `null` |
| `degradado` | Respondió 503: el proceso vive, pero le falla una dependencia | `postgresql`, `redis`, `mongodb` o `bucket` | `null` |
| `caido`     | No respondió, o lo que respondió no es su salud | `proceso` | `sin_conexion`, `tiempo_agotado` o `respuesta_invalida` |

`respuesta_invalida` es una página de error o la salud de otro servicio: el puerto
del directorio no es el de ese servicio. Un servicio detenido sale `caido` con
`sin_conexion`, sin estorbar a los demás.

Errores: un `nombre` que no está en el directorio es 404 `NO_ENCONTRADO`; el historial
con MongoDB caído es 503 `SERVICIO_NO_DISPONIBLE` (con Redis caído sí responde), y la
capacidad con Redis caído también es 503.

## Colas y capacidad (F7)

`/api/v1/services/capacity` (`capacidad.py`) sale de Redis, en una sola lectura:

- **En cola:** el largo de `queue:simulaciones:<motor>` y de sus `:alta` y `:baja`.
- **Vivos:** los `worker:<motor>:<simulador>` que existen. Cada simulador renueva el suyo cada
  10 s y vence a los 30 (`latido_segundos`), así que uno muerto o colgado deja de contar en
  ese lapso. El de `abm-gpu` de la PC con GPU cuenta igual: escribe en el mismo Redis por el
  túnel (D23).
- **Ocupados:** los vivos con `corrida_actual`; `libres` es la diferencia.

Los tres motores salen siempre, aunque no tengan simulador (`MOTORES`, igual a
`procesamiento/contrato.py`; hay prueba). Con corridas en cola y `vivos` en 0, esas corridas
no avanzan: es lo que pasa con `abm-gpu` cuando la PC está apagada.

## Sondeo, Redis y MongoDB

- Un hilo sondea a los 31 a la vez cada `SONDEO_SEGUNDOS` (10 por defecto), con 5 s
  de espera cada uno: en Docker Desktop, el nombre de un contenedor detenido tarda unos
  4 s en no resolverse, así que con Redis caído cada `/health` tarda eso en responder
  503, y con menos espera saldría `caido` en vez de `degradado`.
- El sondeo arranca con `python -m microservicios.estado_servicios`, el `CMD` del
  contenedor, igual que el trabajador de `simulador`. Importar la app no lo prende,
  así que las pruebas no lo ven.
- `health:<servicio>` guarda el último sondeo, y vence a los tres intervalos (30 s):
  si el hilo se detiene, la salud no se queda congelada en verde.
- Cada sondeo es un documento de `historial_servicios` en MongoDB: `servicio`,
  `fecha`, `estado`, `latencia_ms`, `version`, `dependencias_caidas`, `error` y
  `version_esquema`. El índice TTL lo borra a los 30 días. Si MongoDB no responde, el
  sondeo sigue y solo se pierde el historial de ese lapso (D19).
- `/services/health` sondea en ese momento lo que no encuentra en Redis: si venció,
  si Redis está caído o si el hilo no ha corrido. Por eso responde aunque Redis
  esté caído; en ese caso cada consulta sondea a los 31 y tarda unos 8 s (los 4 s
  de no encontrar a Redis, más el sondeo).

Los 30 están en `SERVICIOS` de `sondeo.py`, con su perfil y su puerto. Una prueba
revisa que coincidan con el catálogo y con el compose. Un servicio nuevo del
catálogo se agrega ahí.

## Alertas técnicas (F7)

Cada ronda del sondeo pasa por `alertas.py`. Cuando un servicio cambia de estado (`ok`,
`degradado` o `caido`), los ADMINISTRADOR reciben un aviso `SYSTEM` de `notificaciones`, por
ejemplo «zonas está caído» con «zonas: en línea → caído (proceso, sin conexión)». Lo ven en la
bandeja de avisos del escritorio y de la móvil (`GET /api/v1/notifications`). Para que no sea
ruido:

- **Se confirma:** el cambio tiene que durar 3 rondas (30 s). Reiniciar un contenedor al
  actualizar no avisa.
- **Gracia al arrancar:** los primeros 2 min no avisa, mientras se levanta todo.
- **Un aviso por ronda:** si se degradan los 31 a la vez (Redis caído), llega uno solo.
- **Espera entre fallas:** de un mismo servicio, una falla nueva se avisa 10 min después de la
  anterior como pronto (si sigue). Que se recuperó se avisa siempre.
- **No se repite al reiniciar:** lo último avisado de cada servicio se guarda en
  `alert:<servicio>` (7 días).
- **No se pierde si `notificaciones` no responde:** los cambios esperan y se mandan juntos cada
  60 s hasta que responda. Eso cubre a Redis y PostgreSQL caídos (sin ellos `notificaciones` no
  acepta avisos): el aviso llega cuando vuelven, con todo el recorrido, «auth: en línea →
  degradado (redis) → en línea». Lo que espera vive en la memoria: si `estado-servicios` se
  reinicia en ese lapso, se pierde (el historial sí lo tiene).

Usa un token de servicio (`sub` = `estado-servicios`). Se apagan con `ALERTAS_TECNICAS=0`, y
fuera de Docker, sin `SERVICIO_NOTIFICACIONES_URL`, no se prenden.

## Variables

`DATABASE_URL` (para su `/health`), `JWT_SECRET_KEY` y `REDIS_URL`, como todos, y
`MONGO_URL` para el historial. Además:

| Variable          | Por defecto                 | Qué es |
|-------------------|-----------------------------|--------|
| `URL_PUBLICA`     | `http://{host}:{puerto}`    | La URL que da el directorio a las apps y a la consola |
| `URL_SONDEO`      | `http://127.0.0.1:{puerto}` | Dónde sondea; en el compose, `http://{servicio}:8000` |
| `SONDEO_SEGUNDOS` | `10`                        | Cada cuánto sondea |
| `SERVICIO_NOTIFICACIONES_URL` | — (en el compose, `http://notificaciones:8000`) | A dónde manda las alertas técnicas; sin ella no hay alertas |
| `ALERTAS_TECNICAS` | `1`                        | `0` apaga las alertas técnicas |

Detrás de nginx (D25, RF-K11), `URL_PUBLICA=https://<dominio>/{servicio}` hace que el directorio
responda `https://<dominio>/<servicio>`, con `/docs` y `/openapi.json` debajo.

`/api/v1/services/health` agrega a cada servicio `errores`: las respuestas 5xx de las últimas
24 h (`errors:<servicio>`, ver `comun/README.md`), o vacío si Redis no responde. En `causas`
pueden salir también `mongodb` y `bucket` cuando el `/health` del servicio los reporta caídos o
`no_configurado`.

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
curl "http://127.0.0.1:5262/api/v1/services/capacity?format=json"
```

Fuera de Docker sondea `127.0.0.1` en el puerto de cada servicio, así que ve a los
que estén corriendo en tu máquina.
