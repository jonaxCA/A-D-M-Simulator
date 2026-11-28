# epidemia_comun

Código que repiten los 31 microservicios: formatos, errores, tokens, `/health` y la
plantilla (bloque A), y **Redis** (bloque K).
**No es todavía un despliegue ni una prueba de aceptación completa.**

## Funciones disponibles (bloque A)

- `cargar_ajustes(nombre)`: lee secreto JWT y Redis; se detiene si falta configuración.
- `responder(datos, raiz)` y `leer_cuerpo()`: XML por defecto, JSON con `?format=json`, lectura segura de XML.
- `ErrorAPI` y `respuesta_error`: errores estándar JSON/XML sin revelar trazas.
- `requiere_token(roles=...)` y `solo_servicios`: verifican JWT HS256, audiencia, vencimiento, sesión en Redis y rol.
  Cuando el rol no alcanza, `requiere_token` responde 403 y anota `PERMISSION_DENIED` en la bitácora
  (servicio, ruta, método y roles pedidos; RF-A05, D36). Si la base no responde, el 403 sale igual.
  En las pruebas, el fixture `negados` de `microservicios/conftest.py` recoge esos eventos.
- `token_servicio(app.config, "simulador")`: firma un token de servicio (audiencia interna, 60 s) para
  llamar con `llamar(..., token=...)` a una ruta con `@solo_servicios` cuando no hay persona detrás.
- `crear_app(nombre, contrato, registrar_rutas, dependencias=())`: Flask con `/health`, `/docs` y
  `/openapi.json`. Ver «Salud», «Errores contados» y «Detrás de nginx».
- `filtros_ambito(args, periodos, catalogos=...)` y `clave_ambito(filtros)`: valida `disease_id`,
  `region_id` y `days` (422 si no son válidos, 404 si la enfermedad o el municipio no existen).
  Los catálogos los consulta el servicio con lo que pasa en `catalogos` (`get_enfermedad` y
  `get_region_municipio`), sin `backend_web` (E8). La usan `series` y `zonas`.

- `conversion.entero(valor, errores, etiqueta=..., minimo=..., maximo=...)`, `decimal`, `fecha` y
  `numero_de_esquema`: leen un número o una fecha del texto de un formulario y anotan en `errores`
  el motivo en español. Es copia de `backend_web/conversion.py` (`test_copias_del_monolito.py`). La
  usan `intervenciones` y `validacion` (E8).

- `archivos.guardar(objeto, datos, tipo)`, `leer(objeto)`, `borrar(objeto)`, `url_firmada(objeto,
  minutos=15, nombre=None)` y `ping()`: los archivos en disco o en Cloud Storage (D30). Ver «Archivos».

- `alcance.regiones_permitidas()`, `exige_region(region_id)` y `exige_region_de(obtener)`: el cliente
  técnico de `GET /api/v1/scopes/me` de `roles` (D43). `None` es una cuenta nacional; si no, el
  conjunto de regiones cubiertas. Pide el alcance en cada petición con el token de la persona y, si
  `roles` no responde, es 503: nunca deja pasar. Qué región tiene un dato lo decide cada servicio
  con su SQL. En las pruebas, el fixture `alcance_falso` (autouse) responde nacional.

`microservicios/conftest.py` trae para las pruebas de los servicios un fakeredis compartido
por `crear_app` y `redis_compartido` (`redis_falso`, con `apagar_redis()` para simular la
caída), un firmador de tokens con sesión (`token`) y `crear_cliente("<paquete>")`.

## Salud (`/health`, RF-K10)

Responde `servicio`, `version`, `estado` (`ok` o `degradado`, con 200 o 503), `postgresql` y `redis`
(booleanos, como siempre) y, nuevos, `mongodb` y `bucket`, `tiempos_ms` (milisegundos de cada
comprobación) y `tiempo_ms` (el total). `mongodb` y `bucket` valen:

| Valor             | Significa |
|-------------------|-----------|
| `"no_usa"`        | El servicio no declara esa dependencia |
| `true` / `false`  | La declara y responde / no responde (`false` pone el servicio en `degradado`) |
| `"no_configurado"`| La declara pero falta su URL (también `degradado`) |

Un servicio declara lo que usa con `crear_app(..., dependencias=("mongodb",))` o, sin tocar
código, con la variable `DEPENDENCIAS=mongodb,bucket`. Hoy declaran MongoDB `simulador`,
`resultados` y `estado-servicios`. Las comprobaciones viven en `salud.py`: MongoDB hace un `ping`
con el cliente de `mongo.py` (ver «MongoDB» abajo); el bucket, con `archivos.ping()` (ver «Archivos»
abajo): con `ARCHIVOS=gcs` lista un objeto de `BUCKET_NOMBRE` (lo que permite `storage.objectAdmin`); sin nombre es `no_configurado`. Hoy lo
declara `evidencias`, con `DEPENDENCIAS=bucket` en el compose.

## Errores contados (RF-K12)

Cada respuesta 5xx (menos las de `/health`) suma uno a `errors:<servicio>` en Redis, con TTL de 24 h
desde el primer error de la ventana. `estado-servicios` lo muestra como `errores` en
`/api/v1/services/health` y la consola, en la columna «Errores (24 h)». Con Redis caído no se
cuenta (best-effort).

## Conexiones a PostgreSQL (F4)

`bd.get_conn()` (y `backend_web.db.get_conn()`, que usan la web y los servicios de D que aún la importan)
presta una conexión de `conexiones.py` en lugar de abrir una por consulta: abrirla cuesta unos
47 ms y usarla, menos de 1 ms. Cada proceso guarda hasta `DB_CONEXIONES_LIBRES` (4) por URL;
antes de prestar una comprueba que siga viva, al devolverla hace `rollback` (lo no confirmado se
descarta, como al cerrarla) y si algo falla a la mitad la cierra. Si no hay libres abre otra, sin
esperar. Por eso nadie debe dejar estado de sesión en la conexión (`SET` fuera de una
transacción, tablas temporales, `autocommit`). PostgreSQL acepta 200 conexiones en el compose.
Lo encontró la prueba de carga en la nube: cada página de la web abría varias, el mapa 53.

## Detrás de nginx (D25, RNF-H16)

Con `DETRAS_DE_PROXY=1`, `crear_app` pone `ProxyFix` (`x_for`, `x_proto`, `x_host`, `x_prefix`, un
solo proxy). Así `/docs` apunta a `<prefijo>/openapi.json`, el `servers` de `/openapi.json` pasa a
`https://<dominio>/<servicio>` y los límites de consumo ven la IP real de `X-Forwarded-For`. Sin la
variable esas cabeceras se ignoran, para que nadie falsee su IP. nginx debe mandar
`X-Forwarded-For`, `-Proto`, `-Host` y `-Prefix` (`/<servicio>`). El CORS no cambia: compara el
`Origin` del navegador con `CONSOLE_ORIGIN`, que detrás de nginx es `https://<dominio>`.

**Solo se activa si los puertos de los servicios no están publicados** (compose de producción, F1): si un cliente llega directo al puerto, pone su propio `X-Forwarded-For` y falsea su IP, con lo que se evaden el límite de `/auth/login` y la auditoría. nginx debe sobrescribir la cabecera con `proxy_set_header X-Forwarded-For $remote_addr;` para que `x_for=1` sea fiable. Sin la variable y detrás de nginx, todas las peticiones comparten la IP del proxy.

## Instalación dentro del entorno de desarrollo

Desde la raíz del proyecto:

```bash
pip install -r microservicios/comun/requirements.txt
export PYTHONPATH="$PWD/microservicios/comun:$PWD"
python -m pytest microservicios -q
```

Variables necesarias: `JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL`; `MONGO_URL` en los que usan
MongoDB; opcionales: `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_AUDIENCE_INTERNA`, `MONGO_TIMEOUT_MS`.

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

---

# Redis (bloque K)

Ningún servicio crea su propio `redis.Redis`: todo pasa por estos módulos.

## Instalar y configurar

```bash
pip install -e microservicios/comun[pruebas]
```

| Variable | Para qué | Si falta |
|---|---|---|
| `REDIS_URL` | `redis://:<contraseña>@redis:6379/0` dentro del compose; `redis://:<contraseña>@127.0.0.1:6380/0` desde tu máquina | `redis://127.0.0.1:6379/0` |
| `REDIS_TIMEOUT_SECONDS` | Cuánto espera una operación antes de dar Redis por caído | `0.5` |

Para levantar Redis, copia `infra/.env.example` a `infra/.env`, escribe la contraseña y corre:

```bash
docker compose -f infra/docker-compose.yml up -d redis
```

## Qué hay y qué pasa si Redis se cae

| Módulo | Para qué | Redis caído |
|---|---|---|
| `sesiones` | Solo lo técnico: `verificar(sid, jti)` y `cerrar_de_usuario(usuario)`, el cliente de la ruta interna de `sesiones`. Las reglas (abrir, renovar, cerrar, tope de concurrentes) son del servicio `sesiones` (`microservicios/sesiones/almacen.py`) | 503 |
| `contratos` | `proyectar(fila, campos)`: recorta una fila a los campos del contrato | — |
| `cache` | `obtener(servicio, clave, ttl, calcular)` | Calcula con la base y sigue |
| `candados` | `with candado(llave, ttl):` | 503 |
| `cola` | `encolar`, `tomar` (espera hasta `ESPERA` segundos), `pendientes` | 503 |
| `limites` | `consumir(usuario)` (lo llama `@requiere_token`) y `@limitar(perfil)` para rutas sin sesión, por IP | Sin sesión no se limita; con sesión ya da 503 |
| `llaves` | El nombre de cada llave del catálogo y `huella()` | — |
| `redis_compartido` | `requerido()`, `opcional()`, `estado()` para `/health` | — |

Las excepciones traen `codigo` y `http`, para que el manejador de errores del bloque A3 las
convierta en RFC 7807 sin conocerlas una por una:

| Excepción | `codigo` | `http` |
|---|---|---|
| `redis_compartido.RedisNoDisponible` | `REDIS_NO_DISPONIBLE` | 503 |
| `sesiones.almacen.RefreshReutilizado` (servicio `sesiones`) | `TOKEN_REVOCADO` | 401 |
| `candados.CandadoOcupado` | `CONFLICTO` | 409 |
| `errores.ErrorAPI` desde `limites` | `LIMITE_EXCEDIDO` (con `Retry-After`) | 429 |

## Cómo se usa

```python
from epidemia_comun import cache, candados, cola, llaves, sesiones
from epidemia_comun.redis_compartido import opcional

# @requiere_token, después de revisar la firma: "vigente", "revocado" o "sin_sesion".
estado = sesiones.verificar(claims["sid"], claims["jti"])

# usuarios y roles, al cambiar los roles o dar de baja una cuenta: llama a la ruta interna de
# `sesiones` (DELETE /api/v1/sessions/user/{id}) y regresa cuántas cerró.
cerradas = sesiones.cerrar_de_usuario(usuario_id)

# zonas: la clave lleva todo lo que cambia la respuesta, incluido el ámbito de quien pregunta.
filas = cache.obtener("zonas", f"pagina={pagina}&ambito={ambito}", 60,
                      lambda: consultas.get_monitoreo_zonas(pagina=pagina, **ambito))

# corridas: un doble clic no lanza dos corridas de la misma versión.
with candados.candado(llaves.candado_corrida(version_id), ttl=10):
    corrida_id = crear_corrida(version_id)  # revisa en PostgreSQL y hace commit
    cola.encolar(llaves.cola_simulaciones(motor),
                 json.dumps({"id": corrida_id, "forzar_error": False}))

# simulador: tomar() regresa el texto encolado, o None si no llegó nada.
pedido = cola.tomar(llaves.cola_simulaciones("seir-ref"))
opcional("progreso", lambda r: r.set(llaves.progreso(corrida_id), 40, ex=86400))
```

Notas:

- **Sesión.** Dura `ttl` segundos desde el login, y renovar no la alarga. En Redis solo está la
  huella del `sid` y del *refresh*.
- **Cerrar.** Al cerrar una sesión, sus access dejan de valer, porque `verificar()` revisa que
  siga abierta.
- **Caché.** Conserva `Decimal`, `date` y `datetime`; una tupla regresa como lista. No hay
  invalidación: el monolito escribe directo en la base, así que lo viejo lo limita el TTL.
- **Colas.** Hay una por motor de simulación, y son las únicas llaves sin TTL. Lo que manda es
  PostgreSQL: si la cola se pierde, se vuelve a llenar con las corridas en `encolado`.
- **Llaves nuevas.** Van en `llaves.py` y en la tabla del catálogo
  (`docs/arquitectura/microservicios.md`); `test_llaves` revisa que coincidan.

## Pruebas

```bash
python -m pytest microservicios
```

- Corren con fakeredis y no necesitan Docker. Se corren con `pytest` (decisión D14); están
  escritas con `unittest.TestCase`, que `pytest` también corre.
- Para correrlas contra un Redis real, define `REDIS_URL_PRUEBAS` con una base vacía, por
  ejemplo `redis://:<contraseña>@127.0.0.1:6380/15`. Cada prueba la borra al terminar; si no
  está vacía, se saltan.

## Límites de consumo (D31)

Ventana fija en Redis, un contador `ratelimit:<usuario>:<MÉTODO:regla>` (por IP en las rutas
sin sesión). Las cifras son **supuestos de ingeniería**, a ajustar con las pruebas de carga;
se cambian con `LIMITE_<PERFIL>="peticiones/segundos"`.

| Perfil | Por defecto | Dónde |
|---|---|---|
| `normal` | 120 / 60 s | todos los servicios y `GET /auth/captcha` |
| `permisivo` | 600 / 60 s | `casos`, `sincronizacion` |
| `estricto` | 10 / 60 s | escrituras de `corridas` y `calibracion` (las lecturas son `normal`) |
| `publico` | 10 / 60 s | `POST /auth/login` |

Detrás de nginx, `remote_addr` será la IP del proxy: habrá que leer `X-Forwarded-For` entonces.

---

# MongoDB (bloque D, D28)

Ningún servicio crea su propio `MongoClient`: todo pasa por `mongo.py`, y solo para las dos
colecciones de D28 (regla 12 de `microservicios/AGENTS.md`).

| Variable | Para qué | Si falta |
|---|---|---|
| `MONGO_URL` | `mongodb://epidemia:<MONGO_PASSWORD>@mongodb:27017/epidemia?authSource=epidemia` dentro del compose; desde tu máquina, el puerto `27018` | `/health` dice `no_configurado` y toda operación falla como MongoDB caído |
| `MONGO_TIMEOUT_MS` | Cuánto espera para encontrar el servidor y conectarse; las operaciones, cinco veces eso | `2000` |

| Módulo | Para qué | MongoDB caído |
|---|---|---|
| `mongo` | `base()`, `coleccion(nombre)` (crea sus índices la primera vez), `requerido()`, `opcional()`, `ping()` y `usar()` para las pruebas | `requerido` lanza `MongoNoDisponible` (503 `SERVICIO_NO_DISPONIBLE`, lo convierte `crear_app`); `opcional` regresa el defecto |

## Colecciones

`mongo.INDICES` es el diseño en código; `coleccion()` lo aplica.

| Colección | Un documento es | Índices | Vida | Escribe / lee |
|---|---|---|---|---|
| `series_corridas` | Un día de una corrida: `run_id`, `batch_id`, `scenario_id`, `scenario_version_id`, `motor`, `engine_version`, `semilla`, los campos de `CAMPOS_SERIE` (`procesamiento/contrato.py`) y `version_esquema` | `{run_id, dia}` único; `{scenario_version_id, motor, dia}` | La de la corrida | `simulador` (`simulador/serie.py`) / `resultados` (`resultados/serie.py`); el formato es el contrato `docs/contratos/series_corridas/` (D37) |
| `historial_servicios` | Un sondeo: `servicio`, `fecha`, `estado`, `latencia_ms`, `version`, `dependencias_caidas`, `error` y `version_esquema` | `{servicio, fecha}`; `{fecha}` con TTL de 30 días (el TTL solo se pone en un índice de un campo) | 30 días | `estado-servicios` |

- **Versión de esquema.** Cada documento lleva `version_esquema` (hoy 1). Quien lee filtra por las
  versiones que conoce (`CONOCIDAS`).
- **Actualización.** `simulador/serie.py` (`guardar()`) reemplaza por `{run_id, dia}`: volver a guardar una
  corrida (el reintento del simulador) actualiza sus días y no los duplica.
- **Agregación.** `resultados/serie.py` (`banda()`) da p5, mediana y p95 por día entre las corridas de una
  versión y un motor (`$percentile`, MongoDB 7). `estado-servicios` agrega la disponibilidad y la
  latencia de las últimas 24 h de cada servicio.

```python
from epidemia_comun import mongo

# simulador: si MongoDB no responde, opcional() regresa None y la serie queda pendiente.
mongo.opcional("simulador: guardar la serie", lambda: serie.guardar(docs))

# resultados: sin MongoDB, 503.
serie = mongo.requerido("resultados: leer la serie", lambda: serie.leer(run_id))
```

## Archivos (D30)

`archivos.py` guarda los archivos en el bucket de Cloud Storage o en una carpeta, según `ARCHIVOS`, con
la biblioteca oficial `google-cloud-storage`. Solo lo usa `evidencias` (regla 12 de
`microservicios/AGENTS.md`); la base guarda la ruta del objeto y sus metadatos, nunca el archivo.

| Variable | Para qué | Por omisión |
|---|---|---|
| `ARCHIVOS` | `gcs` (el bucket) o `disco` (una carpeta) | `disco` |
| `BUCKET_NOMBRE` | El bucket, con `gcs` | — (`/health` dice `no_configurado`) |
| `STORAGE_EMULATOR_HOST` | Con un valor, habla con el emulador (`http://bucket:4443` en el compose) en vez de GCP | vacía |
| `BUCKET_URL_PUBLICA` | Con el emulador, el host de las URLs firmadas, para que las abra el navegador | el de `STORAGE_EMULATOR_HOST` |
| `ARCHIVOS_DIR` | La carpeta, con `disco` | `/var/lib/epidemia/archivos` |

| Función | Qué hace | Si falla |
|---|---|---|
| `guardar(objeto, datos, tipo)` | Sube los bytes con su `Content-Type`, sin reintentar a ciegas | `BucketNoDisponible` |
| `leer(objeto)` | Los bytes | `FileNotFoundError` si no existe; `BucketNoDisponible` si el bucket no responde |
| `borrar(objeto)` | Lo borra; si no existía, no pasa nada | `BucketNoDisponible` |
| `url_firmada(objeto, minutos=15, nombre=None)` | `(url, vence)`: URL V4 de lectura que vence (RNF-D17), con `Content-Disposition: inline` si trae `nombre` | `BucketNoDisponible`; con `disco` siempre, porque una carpeta no firma |
| `ping()` | Si el bucket responde (lista un objeto, 2 s) o si la carpeta se puede escribir | — |

- **Firma.** En GCP no hay llaves en el `.env`: la biblioteca firma con signBlob de IAM usando la cuenta
  de servicio de la máquina, `epidemia-vm` (necesita el alcance `cloud-platform` y el rol
  `roles/iam.serviceAccountTokenCreator` sobre sí misma; los da `infra/crea_bucket.sh`). Con el
  emulador, que no revisa firmas, firma un firmante falso con la misma forma de V4.
- **Bucket caído.** `crear_app` convierte `BucketNoDisponible` en 503 `SERVICIO_NO_DISPONIBLE` con
  `Retry-After: 5`, como MongoDB.
- **Tiempo.** Cada operación espera hasta 10 s (`ESPERA`); `ping()`, 2 s.

```python
from epidemia_comun import archivos

archivos.guardar("evidencias/418/3f9a.jpg", datos, "image/jpeg")
url, vence = archivos.url_firmada("evidencias/418/3f9a.jpg", nombre="evidencia-12.jpg")
```

Sus pruebas están en `tests/test_archivos.py`. Contra un emulador de verdad:
`EMULADOR_BUCKET_PRUEBAS=http://localhost:4443 python -m pytest microservicios/comun/tests/test_archivos.py`.

## Pruebas

- Con mongomock: `microservicios/conftest.py` trae `mongo_falso` (una base en memoria, con
  `tz_aware` como el cliente real) y `apagar_mongo()` (toda operación falla; `.encender()` lo
  regresa).
- `tests/test_mongo_real.py` demuestra inserción, consulta, actualización, agregación e índices
  contra un MongoDB real; mongomock no tiene `$percentile` ni `explain()`. Se salta sin
  `MONGO_URL_PRUEBAS`, que apunta a la base `epidemia_pruebas`, nunca a `epidemia`:

```bash
MONGO_URL_PRUEBAS="mongodb://epidemia:$(grep '^MONGO_PASSWORD=' infra/.env | cut -d= -f2-)@127.0.0.1:27018/epidemia_pruebas?authSource=epidemia" \
    python -m pytest microservicios/comun/tests/test_mongo_real.py
```

El `$(grep …)` toma la contraseña de `infra/.env` sin mostrarla. En PowerShell, pon en su lugar
el valor de `MONGO_PASSWORD` de ese archivo. Si sale `Authentication failed`, la contraseña no es
la de `infra/.env`, o el volumen de MongoDB se creó con otra: el usuario se crea solo la primera
vez.
