# EPIDEMIA — Manual técnico (segundo parcial, grupo 14:00)

> **Estado:** parcial · 2026-10-13 · Carlos "Charly" Gomez, Luz Colunga, Mauricio Gallardo.
> Cubre los 12 microservicios del grupo y los componentes compartidos. Los datos salen del
> código de `microservicios/`; donde el plan dice otra cosa, se anota en
> [Pendientes](#14-pendientes-y-fuera-de-alcance).

## Índice

1. [Propósito y alcance](#1-propósito-y-alcance)
2. [Arquitectura](#2-arquitectura)
3. [Tecnologías](#3-tecnologías)
4. [Estructura del repositorio](#4-estructura-del-repositorio)
5. [Biblioteca común `epidemia_comun`](#5-biblioteca-común-epidemia_comun)
6. [Catálogo de servicios](#6-catálogo-de-servicios)
7. [Seguridad](#7-seguridad)
8. [Redis](#8-redis)
9. [Contratos y Swagger](#9-contratos-y-swagger)
10. [Instalación](#10-instalación)
11. [Pruebas](#11-pruebas)
12. [Variables de entorno](#12-variables-de-entorno)
13. [Evidencias](#13-evidencias)
14. [Pendientes y fuera de alcance](#14-pendientes-y-fuera-de-alcance)

---

## 1. Propósito y alcance

EPIDEMIA es un simulador de respuesta a epidemias para Nuevo León. En el segundo parcial se
construye una arquitectura de microservicios Flask que expone el sistema a las apps de
escritorio (XML) y móvil (JSON). El monolito web (`frontend_web` + `backend_web`) sigue
funcionando por su cuenta, conectado directo a PostgreSQL, y no consume los servicios.

Este manual cubre lo que le toca al grupo de las 14:00:

- **Servicios:** `auth`, `sesiones`, `usuarios`, `roles`, `enfermedades`, `parametros`,
  `regiones`, `poblacion`, `tipos-intervencion`, `indicadores`, `series` y `zonas`.
- **Componentes:** la biblioteca común, la seguridad entre componentes, Redis y la
  documentación general.

Los servicios de escenarios, simulación, vigilancia y plataforma, la consola, el
`docker-compose` completo, los XSD de escenario, resultado de una corrida, caso y lote de sincronización y las pruebas de integración del flujo completo son del grupo de las 10:00.

## 2. Arquitectura

Resumen; el detalle, con diagramas, está en
[`arquitectura/arquitectura_v2.md`](arquitectura/arquitectura_v2.md).

- Un servicio por tarea, cada uno en su puerto y su contenedor. Escuchan en el 8000 dentro
  del contenedor.
- Los servicios importan las reglas de `backend_web` (consultas, validaciones, bitácora) y no
  las reescriben.
- PostgreSQL guarda los datos; cada servicio tiene su rol con permisos mínimos (migración 026).
- Redis guarda sesiones, revocaciones y la caché de analítica.
- No hay pasarela: el cliente llama a cada servicio en su puerto con un token Bearer.

## 3. Tecnologías

| Tecnología | Versión | Para qué |
|---|---|---|
| Python | 3.12 en la imagen; el código corre en 3.9 | Lenguaje de los servicios y del monolito |
| Flask | 3.1.3 | Cada microservicio |
| PyJWT | 2.7.0 | Firma y verificación de tokens HS256 |
| redis-py | 5.x o 6.x | Cliente de Redis |
| defusedxml | 0.7 | Lectura segura de cuerpos XML |
| xmlschema | 3.4 o mayor | Validación de XML contra XSD (D15) |
| requests | 2.31+ | Llamadas entre servicios (`llamar()`) |
| waitress | 3.0.2 | Servidor WSGI dentro del contenedor |
| Redis | 7.4 (`redis:7.4-alpine`) | Sesiones, revocación y caché |
| PostgreSQL | 15 o mayor | Base de datos |
| Docker | Docker Desktop / Engine con Compose v2 | Un contenedor por servicio y Redis |
| pytest + fakeredis | pytest 7+, fakeredis 2.20+ | Pruebas sin base ni Redis reales |

## 4. Estructura del repositorio

```
backend_web/        reglas de negocio y SQL (los servicios las importan)
procesamiento/      motor SEIR (no lo usan estos 12 servicios)
frontend_web/       monolito web
microservicios/
  comun/            epidemia_comun, scripts y pruebas de la biblioteca
  conftest.py       fakeredis, tokens firmados y crear_cliente() para las pruebas
  <servicio>/       app.py, rutas.py, Dockerfile, README.md y tests/
  pruebas_integracion/  flujo de identidad entre auth, sesiones, usuarios y roles
                    (tipos-intervencion vive en tipos_intervencion/)
docs/
  arquitectura/     microservicios.md (plan), arquitectura_v2.md (lo construido)
  contratos/        <servicio>/openapi.json, ejemplos/ y .xsd; comun/ (XSD compartidos); postman/
datos/postgres/     migraciones (026 = roles por servicio), dump y semillas
infra/              docker-compose.yml (Redis) y .env.example
evidencias/         capturas de Swagger por servicio (ver su README)
```

## 5. Biblioteca común `epidemia_comun`

Vive en `microservicios/comun/epidemia_comun/`. Todo lo que dos servicios repiten va aquí.

**`ajustes`.** `cargar_ajustes(nombre)` lee `.env.shared` de la raíz y el `.env` de la
carpeta del servicio; las variables del entorno tienen prioridad. Se niega a arrancar si
falta `JWT_SECRET_KEY`, si conserva un valor de ejemplo o si falta `REDIS_URL`. Regresa el
emisor (`epidemia-auth`), las audiencias (`epidemia-api` y `epidemia-interno`), el origen de
la consola para CORS y la versión del servicio.

**`fabrica`.** `crear_app(nombre, contrato, registrar_rutas)` arma la app Flask: le pone un
`X-Correlation-ID` a cada petición, registra método, ruta, código, duración y usuario,
convierte toda excepción en un error RFC 7807 sin traza, y agrega `/health` (estado de
PostgreSQL y Redis, 503 si alguno falla), `/openapi.json` (el contrato de `docs/contratos/`)
y `/docs` (Swagger UI). CORS solo para `CONSOLE_ORIGIN`.

**`formatos`.** `responder(datos, raiz)` regresa XML por omisión y JSON con `?format=json` o
`Accept: application/json`; un `?format` desconocido es 400. `a_xml` escapa todo, marca
números (`tipo="numero"`), booleanos (`tipo="booleano"`) y nulos (`nil="true"`), y nombra en
singular los elementos de las colecciones (`zonas` → `zona`). Si la clave de un diccionario
no puede ser etiqueta XML (por ejemplo `0-19` u `80+`), se escribe como
`<entrada clave="0-19" tipo="numero">100</entrada>`; `de_xml` recupera la clave original.
Las claves válidas mantienen las etiquetas anteriores. `leer_cuerpo()` acepta JSON o XML
según el `Content-Type` (otro es 415), con `defusedxml` y un límite de 1 MB.

**`errores`.** `ErrorAPI(estado, codigo, detalle)` y `respuesta_error()`, que la regresa como
`application/problem+json` o `problem+xml` con `type`, `title`, `status`, `detail`, `codigo` e
`instance`.

**`seguridad`.** `verificar_token()` exige HS256, firma, `iss`, `aud`, `exp`, `nbf`, `iat`,
`jti` y `sub`; revisa en Redis que el `jti` no esté revocado y que la sesión siga abierta, y
compara los roles. `@requiere_token(roles=...)` lo aplica a una ruta y deja en `g` el usuario
y el `Contexto` (usuario, IP, user agent) para la bitácora. `@solo_servicios` acepta solo
tokens de audiencia `epidemia-interno`.

**`sesiones`.** `abrir`, `obtener`, `renovar`, `cerrar`, `cerrar_todas`, `revocar` y
`verificar`. Guarda en Redis solo huellas SHA-256 del `sid` y del refresh. `renovar` rota el
refresh dentro de una transacción vigilada; uno ya usado lanza `RefreshReutilizado` y cierra
la sesión.

**`redis_compartido`.** Un cliente por proceso (`REDIS_URL`, timeout de 0.5 s, un reintento).
`requerido()` convierte una falla de Redis en `RedisNoDisponible` (503); `opcional()` regresa
un valor por omisión y deja seguir. `estado()` alimenta la salud. `usar()` permite inyectar
fakeredis en las pruebas.

**`cache`.** `obtener(servicio, clave, ttl, calcular)` lee `cache:<servicio>:<clave>`; si no
está la calcula y la guarda con TTL. Si Redis no responde, calcula con la base. Conserva
`Decimal` y fechas. No hay invalidación: lo viejo lo limita el TTL.

**`candados` y `cola`.** Candado con TTL (`with candado(llave, ttl)`, 409 si está tomado) y la
cola de corridas (`encolar`, `tomar`, `pendientes`). Los usarán `corridas` y `simulador`.

**`llaves`.** El nombre de cada llave de Redis del catálogo y `huella()`. Una prueba revisa
que coincidan con la tabla de `docs/arquitectura/microservicios.md`.

**`http`.** `llamar(servicio, metodo, ruta, formato, cuerpo)` llama a otro servicio (URL en
`SERVICIO_<NOMBRE>_URL`), reenvía el token y el `X-Correlation-ID` de la petición, y convierte
un servicio caído en 503 `SERVICIO_NO_DISPONIBLE`. No reintenta.

**`validaciones`.** `diccionario`, `entero_positivo` y `parametros_epidemiologicos` (cada
parámetro con valor numérico en rango, y fuente o `supuesto: true`; las tasas como fracción).

**`ambito`.** `filtros_ambito()` valida `disease_id`, `region_id` y `days` para `series` y
`zonas` (422 fuera de dominio, 404 si no existe) y `clave_ambito()` arma la parte de la llave
de caché.

## 6. Catálogo de servicios

Todos responden XML por omisión y JSON con `?format=json`, sirven `/health`, `/docs` y
`/openapi.json`, y regresan errores RFC 7807. Además de los de cada uno: 400 (`?format`
desconocido), 415 (cuerpo que no es JSON ni XML) y, en rutas con token, 401 (`TOKEN_AUSENTE`,
`TOKEN_INVALIDO`, `TOKEN_EXPIRADO`, `TOKEN_REVOCADO`), 403 (`PERMISO_INSUFICIENTE`) y 503 si
Redis no responde.

### Identidad

#### `auth` · 5201

| Método | Ruta | Acceso | Entrada | Salida |
|---|---|---|---|---|
| GET | `/api/v1/auth/captcha` | Público | — | `captcha_id`, `pregunta` ("3 + 5"), `expira` |
| POST | `/api/v1/auth/login` | Público | `usuario`, `password`, `captcha_id`, `captcha_respuesta` | `access_token`, `refresh_token`, `token_type`, `expires_in` (1200), `sesion_expira`, `usuario` |

- Errores: 422 (campo faltante o captcha incorrecto/vencido), 401 `CREDENCIALES_INVALIDAS`
  (mismo mensaje para contraseña equivocada, cuenta inactiva o bloqueada), 503 sin Redis.
- El captcha se revisa antes que la contraseña y sirve una sola vez. Cinco intentos fallidos
  bloquean la cuenta 15 minutos (`backend_web.auth`).
- Bitácora: `LOGIN` y `LOGIN_FAILED`.
- Redis: `captcha:<id>` (300 s); abre `session:`, `refresh:` y `user:<id>:sessions` (8 h).

#### `sesiones` · 5202

| Método | Ruta | Acceso | Entrada | Salida |
|---|---|---|---|---|
| POST | `/api/v1/sessions/refresh` | Público (el refresh es la credencial) | `refresh_token` | access y refresh nuevos, `sesion_expira` |
| POST | `/api/v1/sessions/logout` | Token, cualquier rol | — | `cerrada: true` |
| GET | `/api/v1/sessions/current` | Token, cualquier rol | — | `usuario`, `roles`, `creada`, `expira`, `access_expira` |
| DELETE | `/api/v1/sessions/user/{id}` | Solo token de servicio | — | `usuario`, `cerradas` |

- Errores: 422 (falta `refresh_token` o id inválido), 401 `TOKEN_INVALIDO` (refresh
  desconocido o vencido), 401 `TOKEN_REVOCADO` (refresh reutilizado: la sesión se cierra).
- Bitácora: `LOGOUT`.
- Redis: `session:`, `refresh:`, `refresh:usado:`, `jwt:revoked:<jti>` (lo que le quede al
  token más 60 s).

#### `usuarios` · 5203

Todas las rutas: ADMINISTRADOR.

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| GET | `/api/v1/users` | `q`, `role_id`, `status` (activo, pendiente, inactivo) | `total`, `usuarios` |
| GET | `/api/v1/users/{id}` | — | la cuenta y sus `roles` |
| POST | `/api/v1/users` | `username`, `email`, `full_name`, `password`, `is_active` | la cuenta (201) |
| PUT | `/api/v1/users/{id}` | `email`, `full_name`, `password` | la cuenta y `sesiones_cerradas` |
| POST | `/api/v1/users/{id}/activate` · `/deactivate` | — | `id`, `is_active`, `sesiones_cerradas` |
| DELETE | `/api/v1/users/{id}` | — | `id`, `eliminado`, `sesiones_cerradas` |

- Errores: 404, 409 (usuario o correo duplicado, cuenta con dependencias, desactivarse o
  borrarse a sí mismo), 422.
- Nunca regresa ni audita `password_hash`. El username no se edita; el rol se asigna en
  `roles`. Cambiar la contraseña, desactivar o borrar cierra las sesiones de la cuenta.
- Bitácora: `CREATE`, `UPDATE`, `DELETE` sobre `users`. Redis: `user:<id>:sessions`.

#### `roles` · 5204

Todas las rutas: ADMINISTRADOR.

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| GET | `/api/v1/roles` | — | `total`, `roles` |
| GET | `/api/v1/roles/{id}/permissions` | — | el rol y sus `permisos` (`code`, `resource`, `action`, `description`) |
| PUT | `/api/v1/roles/assignments/{user_id}` | `role_id` | `user_id`, `role_id`, `sesiones_cerradas` |

- Un rol por cuenta. Errores: 404 (rol o usuario), 409 (quitarse a sí mismo el rol de
  administrador), 422.
- Al cambiar el rol se cierran las sesiones: los access llevan los roles con que se emitieron.
- Bitácora: `UPDATE` sobre `users` con `role_ids` antes y después.

### Catálogos

#### `enfermedades` · 5211

| Método | Ruta | Acceso | Entrada | Salida |
|---|---|---|---|---|
| GET | `/api/v1/diseases` | Público | `q`, `status` (activa, inactiva), `page`, `size` (máx. 100) | página con `enfermedades` (actividad y estado de parámetros) |
| GET | `/api/v1/diseases/{id}` | Público | — | `id`, `code`, `name`, `description`, `is_active`, `created_at` |
| POST | `/api/v1/diseases` | EPIDEMIOLOGO, ADMINISTRADOR | `code`, `name`, `description` | `id` (201) |
| PUT | `/api/v1/diseases/{id}` | EPIDEMIOLOGO, ADMINISTRADOR | `name`, `description` | `id`, `actualizada` |
| POST | `/api/v1/diseases/{id}/activate` · `/deactivate` | EPIDEMIOLOGO, ADMINISTRADOR | — | `id`, `is_active` |

- El código no se edita y no hay `DELETE`: la baja es lógica. Los parámetros se cambian en
  `parametros`.
- Errores: 404, 409 (código duplicado), 422 (código fuera de formato, campos de más).
- Bitácora: `CREATE` y `UPDATE` sobre `diseases`.

#### `parametros` · 5212

| Método | Ruta | Acceso | Entrada | Salida |
|---|---|---|---|---|
| GET | `/api/v1/diseases/{id}/parameters` | Público | — | `disease_id`, `parametros` |
| GET | `/api/v1/diseases/{id}/parameters/status` | Público | — | `detalle`, `informativos`, `faltan`, `supuestos`, `sin_fuente`, `simulable` |
| PUT | `/api/v1/diseases/{id}/parameters` | EPIDEMIOLOGO, ADMINISTRADOR | `parametros: {clave: {valor, fuente, supuesto}}` | los parámetros guardados |

- Cada valor lleva fuente o `supuesto: true`; si no, 422. Las tasas van como fracción (0 a 1).
  Los parámetros no enviados se conservan; `null` borra uno.
- Solo escribe `diseases.default_params`. Bitácora: `UPDATE` sobre `diseases`.

#### `regiones` · 5213

| Método | Ruta | Acceso | Entrada | Salida |
|---|---|---|---|---|
| GET | `/api/v1/regions` | Público | `q`, `order` (nombre, poblacion, poblacion_60), `direction` (asc, desc) | los 51 `municipios` con su población, 60+ y la fuente de cada cifra |
| GET | `/api/v1/regions/{id}` | Público | — | el municipio |

- Solo lectura; no usa Redis, así que responde aunque Redis esté caído. Errores: 404, 422.

#### `poblacion` · 5214

| Método | Ruta | Acceso | Entrada | Salida |
|---|---|---|---|---|
| GET | `/api/v1/regions/{id}/population` | Público | — | `region_id`, `population`, `population_60plus` |
| PUT | `/api/v1/regions/{id}/population` | ADMINISTRADOR | `population`, `expected_population`, `reason` | antes, después y si cambió el estado |
| GET | `/api/v1/regions/{id}/age-groups` | Público | — | `grupos` (0-19 … 80+) y `edad_no_especificada` |
| PUT | `/api/v1/regions/{id}/age-groups` | ADMINISTRADOR | `groups`, `expected_groups`, `reason` | municipio, 60+ derivado y si cambió el estado |

- Control de concurrencia: si el valor esperado ya no coincide, 409 `CONFLICTO`.
- Errores: 404, 409, 422 (población negativa o menor que su 60+, motivo vacío).
- La corrección recalcula el agregado de Nuevo León en la misma transacción. Bitácora:
  `UPDATE` sobre `regions`.

#### `tipos-intervencion` · 5215

| Método | Ruta | Acceso | Salida |
|---|---|---|---|
| GET | `/api/v1/intervention-types` | Público | `total`, `tipos` con su `param_schema` (JSON Schema) y costo |
| GET | `/api/v1/intervention-types/{code}` | Público | un tipo; el código se acepta en minúsculas |

Errores: 404 (código inexistente, inactivo o fuera de formato).

### Analítica

#### `indicadores` · 5251

| Método | Ruta | Acceso | Entrada | Salida |
|---|---|---|---|---|
| GET | `/api/v1/dashboard/indicators` | Público | — | casos activos, tasa por 100k, zonas en riesgo, simulaciones activas y su variación |
| GET | `/api/v1/dashboard/situation` | Público | `limit` (1 a 20, 5 por omisión) | `enfermedades` con su tendencia (estable, alerta, critico) |

Errores: 422. Redis: `cache:indicadores:*` (60 s); sin Redis responde desde la base.

#### `series` · 5252

Todas las rutas: token de cualquier rol. Filtros: `disease_id`, `region_id`, `days` (7, 30 o
90; 30 por omisión).

| Método | Ruta | Salida |
|---|---|---|
| GET | `/api/v1/series/cases` | `puntos`: casos por día e incidencia acumulada |
| GET | `/api/v1/series/cases/by-age` | los seis `grupos` de edad en orden |
| GET | `/api/v1/series/cases/by-sex` | `sexos` con casos y porcentaje |
| GET | `/api/v1/series/cases/totals` | periodo contra periodo previo |

Errores: 404 (enfermedad o municipio inexistente), 422. Redis: `cache:series:*` (60 s).

#### `zonas` · 5253

Ambas rutas: token de cualquier rol.

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| GET | `/api/v1/zones` | filtros de `series`, `q`, `order` (casos, incidencia), `page`, `size` (máx. 100) | `zonas` con semáforo y `mayor_cambio` (`con_aumento`, `sin_aumento`, `sin_casos`) |
| GET | `/api/v1/zones/map` | `disease_id`, `days` (7, 30 o 60) | `municipios` con nivel y tendencia, y la `serie` diaria |

`mayor_cambio` se calcula sobre todas las zonas, no sobre la página (LIMP-20). Errores: 404,
422. Redis: `cache:zonas:*` (60 s).

## 7. Seguridad

- **JWT de acceso:** HS256 con `JWT_SECRET_KEY`, 20 minutos. Claims `iss`, `aud`
  (`epidemia-api`), `sub`, `roles`, `sid`, `jti`, `iat`, `nbf` y `exp`.
- **Sesión y refresh:** la sesión dura 8 horas desde el login y renovar no la alarga. Cada
  refresh sirve una vez: `sesiones` lo rota y, si alguien reutiliza uno viejo, cierra la
  sesión completa.
- **Revocación:** logout guarda `jwt:revoked:<jti>` y borra la sesión; cerrar una sesión
  invalida todos sus access porque cada ruta protegida revisa que siga abierta.
- **Token de servicio:** para llamadas sin persona detrás. Audiencia `epidemia-interno`, sin
  `sid`; solo lo aceptan las rutas `@solo_servicios`, y esas rechazan el token de una persona.
  Hay pruebas para los dos rechazos en `comun/tests/test_seguridad.py`.
- **Rechazos probados:** `alg: none`, otra firma, vencido, otra audiencia, revocado, rol
  insuficiente y token de servicio en una ruta de personas.
- **Roles de PostgreSQL:** la migración `026_roles_por_servicio.sql` crea `svc_<servicio>` con
  permisos mínimos. `regiones`, `tipos-intervencion`, `indicadores`, `series` y `zonas` solo
  leen; `parametros` solo puede escribir `diseases.default_params`; `enfermedades`, todo
  `diseases` menos editar `default_params`; `poblacion`, la población y las bandas de edad.
  No toca a `epidemia_app`.
- **Redis caído:** una ruta protegida responde 503 y nunca deja pasar.
- **Bitácora:** cada escritura llama a `log_audit` dentro de su transacción, con usuario e IP
  tomados del token y de la conexión. Nunca se registran tokens ni contraseñas.
- **CORS:** cerrado; solo se abre para `CONSOLE_ORIGIN`.

## 8. Redis

| Llave | Qué guarda | TTL | Escribe |
|---|---|---|---|
| `session:<h(sid)>` | usuario, roles, creada, expira y huella del refresh | 8 h desde el login | `auth`, `sesiones` |
| `user:<id>:sessions` | huellas de las sesiones de una cuenta | 8 h | `auth`, `sesiones`, `usuarios`, `roles` (al cerrar) |
| `refresh:<h(rt)>` | huella del `sid` | lo que le quede a la sesión | `auth`, `sesiones` |
| `refresh:usado:<h(rt)>` | refresh ya rotado | lo que le quede a la sesión | `sesiones` |
| `jwt:revoked:<jti>` | `1` | lo que le quede al token + 60 s | `sesiones` |
| `captcha:<id>` | respuesta del captcha | 300 s | `auth` |
| `cache:<servicio>:<clave>` | respuesta en JSON | 60 s | `indicadores`, `series`, `zonas` |

El contenedor (`infra/docker-compose.yml`) usa Redis 7.4 con contraseña, AOF y
`maxmemory-policy noeviction`, publicado solo en `127.0.0.1:6380`.

## 9. Contratos y Swagger

- Cada servicio tiene `docs/contratos/<servicio>/openapi.json`, el mismo que sirve en
  `/openapi.json`, y Swagger UI en `http://localhost:<puerto>/docs`.
- `enfermedades`, `parametros`, `regiones`, `poblacion`, `tipos-intervencion`, `indicadores`,
  `series` y `zonas` traen un ejemplo JSON y uno XML por ruta en el contrato y en
  `docs/contratos/<servicio>/ejemplos/`.
- XSD (D15), validados con `xmlschema`: `docs/contratos/comun/problem.xsd` (el error de cualquier
  servicio, con los tipos compartidos de `comun/tipos.xsd`), `enfermedades/enfermedad.xsd` y
  `parametros/parametros.xsd`.
- `docs/contratos/postman/` tiene una colección de Postman (también para `newman`) de
  `tipos-intervencion`, `indicadores`, `series` y `zonas`, con su guía.
- En las rutas con candado, pega el token en **Authorize**. Abre Swagger con `localhost`, no
  con `127.0.0.1`.

## 10. Instalación

- **Local:** la base, el `.env` y el entorno virtual se instalan con
  [`INSTALACION.md`](INSTALACION.md) (pasos 0 a 4). Un servicio se levanta desde la raíz con
  `PYTHONPATH="$PWD:$PWD/microservicios/comun" python -m microservicios.<carpeta>.app`.
- **Docker:** la sección "Docker: microservicios del grupo 14:00" de
  [`INSTALACION.md`](INSTALACION.md) tiene los pasos exactos con que se levantaron los 12
  servicios: PostgreSQL y Redis en contenedores, la base cargada con `dump_completo.sql`, cada
  servicio con `waitress` y su rol, el login con `auth` y la comprobación de `/health` y
  `/docs`. También cómo construir y correr la imagen de un servicio.
- **Migración 026:** viene dentro de `dump_completo.sql` y también se puede correr sola con
  `psql -f`; es idempotente. Después, fija la contraseña de cada rol con `ALTER ROLE`.

## 11. Pruebas

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios -q
```

No necesitan base ni Redis: `microservicios/conftest.py` inyecta fakeredis en la fábrica y en
`redis_compartido`, firma tokens con un secreto de prueba y cada prueba simula la base con
`monkeypatch`.

**Ejecución de referencia anterior (2026-10-13): 291 pasan y 3 `xfail`**, más
34 subpruebas de la biblioteca. Corresponde al código previo a la corrección XML y se
conserva en `evidencias/pruebas/pytest_microservicios.txt`.

**Resultado posterior a la corrección XML:** 307 passed, 34 subtests passed in 1.64s.
Registro de la ejecución en `evidencias/pruebas/pytest_microservicios_xml_corregido.txt`.

**Con la validación XSD:** 322 passed (`evidencias/pruebas/pytest_microservicios_xsd.txt`).
`comun/tests/test_xsd.py` valida contra los XSD los ejemplos XML de los contratos, respuestas
reales de `enfermedades` y `parametros` (en todos los formatos de parámetros que conviven en la
base) y los errores 401 y 404, y comprueba que un documento inválido se rechace.

**Con las pruebas de integración iniciales (resultado actual):** 325 passed
(`evidencias/pruebas/pytest_microservicios_integracion.txt`).

| Dónde | Qué cubren |
|---|---|
| `comun/tests/` | Formatos, errores, ajustes, tokens (`alg: none`, firma, vencido, audiencia, revocado, rol, token de servicio en ruta de personas y de persona en `@solo_servicios`), sesiones, caché, candados, cola, llaves, Redis caído, contratos, ejemplos y XSD |
| `auth`, `sesiones`, `usuarios`, `roles` | Login con captcha, refresh de un solo uso, logout, ruta interna, altas y bajas con bitácora, asignación de rol |
| `enfermedades`, `parametros`, `regiones`, `poblacion` | XML por omisión, `?format=json` y `Accept`, 400, 401, 403, 404, 409, 422, cuerpos JSON y XML, `log_audit` en cada escritura, el código que no se edita, la baja sin `DELETE`, la fuente o supuesto obligatorio, el control de concurrencia y `regiones` con Redis caído |
| `tipos_intervencion`, `indicadores`, `series`, `zonas` | Formatos, permisos, filtros, caché y Redis caído |
| `pruebas_integracion/` | Integración iniciales: `auth`, `sesiones`, `usuarios` y `roles` juntos, con el mismo Redis y la misma base simulada. Un cambio de rol y una baja cierran las sesiones de la cuenta; el refresh y el logout valen en todos los servicios; con Redis caído todos responden 503 |

Las tres pruebas de XML de `enfermedades`, `parametros` y `poblacion` ya no llevan
`xfail`: ahora verifican XML bien formado y el contenido de `<entrada clave="...">`.
Se añadieron regresiones de serialización y lectura en la biblioteca común.

Los permisos de la 026 se probaron contra una base real, rol por rol:
`evidencias/pruebas/roles_postgres.txt` (21 de 21).

## 12. Variables de entorno

| Variable | Obligatoria | Por omisión | Uso |
|---|---|---|---|
| `JWT_SECRET_KEY` | Sí | — | Firma de los tokens; la misma en todos los servicios |
| `REDIS_URL` | Sí | — (la capa de Redis cae a `redis://127.0.0.1:6379/0`) | Redis; con el compose, `redis://:<REDIS_PASSWORD>@127.0.0.1:6380/0` |
| `DATABASE_URL` | Sí | — | PostgreSQL; con la 026, el usuario `svc_<servicio>` de ese servicio |
| `JWT_ISSUER` | No | `epidemia-auth` | Emisor de los tokens |
| `JWT_AUDIENCE` | No | `epidemia-api` | Audiencia de los tokens de personas |
| `JWT_AUDIENCE_INTERNA` | No | `epidemia-interno` | Audiencia del token de servicio |
| `CONSOLE_ORIGIN` | No | vacío (CORS cerrado) | Único origen al que se abre CORS |
| `VERSION_SERVICIO` | No | `0.1.0` | Versión que reporta `/health` |
| `REDIS_TIMEOUT_SECONDS` | No | `0.5` | Cuánto espera Redis antes de darlo por caído |
| `SERVICIO_<NOMBRE>_URL` | Solo si llama a otro | — | URL de otro servicio para `llamar()` |
| `REDIS_PASSWORD`, `REDIS_PUERTO_LOCAL` | En `infra/.env` | — / `6380` | Contraseña y puerto del Redis del compose |

Las variables se toman del primer lugar donde se encuentren: el entorno, el `.env` de la raíz
(el del monolito, que lee `backend_web`), `.env.shared` en la raíz y
`microservicios/<servicio>/.env`. Como el `.env` de la raíz trae la `JWT_SECRET_KEY` del
monolito, la de los servicios se define en el entorno. Ninguno de esos archivos se sube; las
plantillas son `.env.example` e `infra/.env.example`.

## 13. Evidencias

[`evidencias/README.md`](../evidencias/README.md) es el índice: la salida de las pruebas, los
permisos de la 026 probados en la base y, por cada servicio, las capturas de `/health` y de una
ruta en Swagger en XML y en JSON. Las 12 respondieron 200.

## 14. Pendientes y fuera de alcance

**Fuera de alcance de este parcial:**

- Las apps móvil y de escritorio: se entregan en el tercer parcial.
- MongoDB, Google Cloud Storage y nginx.
- Del grupo de las 10:00: los XSD de escenario, resultado de una corrida, caso y lote de sincronización, las pruebas de integración del flujo completo, el
  `docker-compose` con todos los servicios y la consola.

**Pendientes del grupo 14:00:**

- Volver a verificar con los contenedores de la versión integrada los endpoints cuyo XML se
  corrigió: `GET /api/v1/diseases`, `parametros` con `letalidad_por_edad` y
  `GET /regions/{id}/age-groups`.

**Corregido en esta entrega:**

- Se corrigió la serialización de claves no válidas como etiqueta XML (`0-19`, `80+`)
  en la biblioteca común; `de_xml` reconoce el atributo `clave` para reconstruir el
  diccionario. Las tres pruebas que registraban este problema dejan de ser `xfail`.
- `poblacion`: `PUT /age-groups` descartaba `expected_groups.edad_no_especificada`, que el
  control de concurrencia de `backend_web` compara, y toda corrección terminaba en error.
  Ahora la ruta la valida y la pasa, como la pantalla del monolito.
- `poblacion`: el mensaje de concurrencia "Los datos del municipio cambiaron mientras
  editabas" salía como 422; ahora, como los otros dos, es 409 `CONFLICTO`.
- Migración 026: fallaba en una base real al buscar la secuencia de `user_roles`, que no
  tiene columna `id`. Se corrigió y ya está al final de `dump_completo.sql`.

**Diferencias entre el plan y el código:**

- Ningún servicio emite todavía tokens de servicio; `usuarios` y `roles` cierran sesiones
  directo en Redis en vez de llamar a `DELETE /api/v1/sessions/user/{id}`.
- `@requiere_token` revisa Redis con el cliente de la fábrica, no con `sesiones.verificar()`.
- `auth` usa la ruta `GET /api/v1/auth/captcha` y la llave `captcha:<id>`, que no están en el
  catálogo ni en `llaves.py`.
- Los servicios leen `DATABASE_URL`; para usar su rol de la 026 hay que pasarles la URL con
  `svc_<servicio>`.
- Los servicios no están todavía en `infra/docker-compose.yml` (el compose completo es del
  grupo de las 10:00).
