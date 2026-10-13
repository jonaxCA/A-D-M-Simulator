# epidemia_comun

Código que repiten los 26 microservicios. Por ahora trae **Redis** (bloque K del checklist);
el bloque A agrega formatos, errores, tokens, `/health` y la plantilla.

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
with candados.candado(llaves.candado_corrida(version_id), ttl=30):
    corrida_id = crear_corrida(version_id)  # revisa en PostgreSQL y hace commit
    cola.encolar(llaves.COLA_SIMULACIONES, corrida_id)

# simulador: tomar() regresa el id como texto, o None si no llegó nada.
corrida_id = cola.tomar(llaves.COLA_SIMULACIONES)
opcional("progreso", lambda r: r.set(llaves.progreso(corrida_id), 40, ex=3600))
```

Notas:

- **Sesión.** Dura `ttl` segundos desde el login, y renovar no la alarga. En Redis solo está la
  huella del `sid` y del *refresh*.
- **Cerrar.** Al cerrar una sesión, sus access dejan de valer, porque `verificar()` revisa que
  siga abierta.
- **Caché.** Conserva `Decimal`, `date` y `datetime`; una tupla regresa como lista. No hay
  invalidación: el monolito escribe directo en la base, así que lo viejo lo limita el TTL.
- **Cola.** Es la única llave sin TTL. Lo que manda es PostgreSQL: si la cola se pierde, se
  vuelve a llenar con las corridas en `encolado`.
- **Llaves nuevas.** Van en `llaves.py` y en la tabla del catálogo
  (`docs/arquitectura/microservicios.md`); `test_llaves` revisa que coincidan.

## Pruebas

```bash
python -m pytest microservicios/comun/tests
```

- Corren con fakeredis y no necesitan Docker. Se corren con `pytest` (decisión D14); están
  escritas con `unittest.TestCase`, que `pytest` también corre.
- Para correrlas contra un Redis real, define `REDIS_URL_PRUEBAS` con una base vacía, por
  ejemplo `redis://:<contraseña>@127.0.0.1:6380/15`. Cada prueba la borra al terminar; si no
  está vacía, se saltan.
