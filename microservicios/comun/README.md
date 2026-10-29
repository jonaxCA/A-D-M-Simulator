# epidemia_comun

Código que repiten los 26 microservicios: formatos, errores, tokens, `/health` y la
plantilla (bloque A), y **Redis** (bloque K).
**No es todavía un despliegue ni una prueba de aceptación completa.**

## Funciones disponibles (bloque A)

- `cargar_ajustes(nombre)`: lee secreto JWT y Redis; se detiene si falta configuración.
- `responder(datos, raiz)` y `leer_cuerpo()`: XML por defecto, JSON con `?format=json`, lectura segura de XML.
- `ErrorAPI` y `respuesta_error`: errores estándar JSON/XML sin revelar trazas.
- `requiere_token(roles=...)` y `solo_servicios`: verifican JWT HS256, audiencia, vencimiento, sesión en Redis y rol.
- `token_servicio(app.config, "simulador")`: firma un token de servicio (audiencia interna, 60 s) para
  llamar con `llamar(..., token=...)` a una ruta con `@solo_servicios` cuando no hay persona detrás.
- `crear_app(nombre, contrato, registrar_rutas)`: Flask con `/health`, `/docs` y `/openapi.json`.
- `filtros_ambito(args, periodos)` y `clave_ambito(filtros)`: valida `disease_id`, `region_id`
  y `days` (422 si no son válidos, 404 si la enfermedad o el municipio no existen). La usan
  `series` y `zonas`.

`microservicios/conftest.py` trae para las pruebas de los servicios un fakeredis compartido
por `crear_app` y `redis_compartido` (`redis_falso`, con `apagar_redis()` para simular la
caída), un firmador de tokens con sesión (`token`) y `crear_cliente("<paquete>")`.

## Instalación dentro del entorno de desarrollo

Desde la raíz del proyecto:

```bash
pip install -r microservicios/comun/requirements.txt
export PYTHONPATH="$PWD/microservicios/comun:$PWD"
python -m pytest microservicios -q
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
| `sesiones` | `abrir`, `obtener`, `renovar`, `cerrar`, `cerrar_todas`, `revocar`, `verificar` | 503 |
| `cache` | `obtener(servicio, clave, ttl, calcular)` | Calcula con la base y sigue |
| `candados` | `with candado(llave, ttl):` | 503 |
| `cola` | `encolar`, `tomar` (espera hasta `ESPERA` segundos), `pendientes` | 503 |
| `llaves` | El nombre de cada llave del catálogo y `huella()` | — |
| `redis_compartido` | `requerido()`, `opcional()`, `estado()` para `/health` | — |

Las excepciones traen `codigo` y `http`, para que el manejador de errores del bloque A3 las
convierta en RFC 7807 sin conocerlas una por una:

| Excepción | `codigo` | `http` |
|---|---|---|
| `redis_compartido.RedisNoDisponible` | `REDIS_NO_DISPONIBLE` | 503 |
| `sesiones.RefreshReutilizado` | `TOKEN_REVOCADO` | 401 |
| `candados.CandadoOcupado` | `CONFLICTO` | 409 |

## Cómo se usa

```python
from epidemia_comun import cache, candados, cola, llaves, sesiones
from epidemia_comun.redis_compartido import opcional

# auth, al iniciar sesión: el sid va en el claim `sid` del access; la app guarda el refresh.
s = sesiones.abrir(usuario["id"], usuario["roles"], ttl=7200)

# @requiere_token, después de revisar la firma: "vigente", "revocado" o "sin_sesion".
estado = sesiones.verificar(claims["sid"], claims["jti"])

# sesiones, logout: el access deja de valer aunque no haya vencido.
sesiones.revocar(claims["jti"], claims["exp"])
sesiones.cerrar(claims["sid"])

# sesiones, refresh: None si no existe o venció. Si ya se había usado, lanza
# RefreshReutilizado y la sesión queda cerrada.
nueva = sesiones.renovar(refresh)

# usuarios y roles, al cambiar los roles o dar de baja una cuenta (por la ruta interna de sesiones).
sesiones.cerrar_todas(usuario_id)

# zonas: la clave lleva todo lo que cambia la respuesta, incluido el ámbito de quien pregunta.
filas = cache.obtener("zonas", f"pagina={pagina}&ambito={ambito}", 60,
                      lambda: queries.get_monitoreo_zonas(pagina=pagina, **ambito))

# corridas: un doble clic no lanza dos corridas de la misma versión.
with candados.candado(llaves.candado_corrida(version_id), ttl=10):
    corrida_id = crear_corrida(version_id)  # revisa en PostgreSQL y hace commit
    cola.encolar(llaves.cola_simulaciones(motor),
                 json.dumps({"id": corrida_id, "forzar_error": False}))

# simulador: tomar() regresa el texto encolado, o None si no llegó nada.
pedido = cola.tomar(llaves.cola_simulaciones("python-ref"))
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
