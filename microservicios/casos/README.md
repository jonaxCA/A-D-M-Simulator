# EPIDEMIA - Servicio casos

Puerto externo 5221; puerto interno en Docker, 8000. Registra, consulta y corrige casos
epidemiológicos y cambia su estado, con control de versión e historial (tablas `cases` y
`case_history`, D47), y administra los formularios de captura de cada enfermedad (`case_forms`,
D48). Es el único servicio que escribe en ellas.

## Rutas (`/api/v1`)

| Ruta | Roles | Qué hace |
|---|---|---|
| `POST /cases` | CAPTURISTA (D1: el ADMINISTRADOR no captura) | Valida con `queries.valida_caso` (catálogo vigente de enfermedades y municipios, fechas, rangos, coordenadas completas), inserta con `status = pendiente` y deja un `CREATE` en `audit_log`, en la misma transacción. `reported_by` sale del token. |
| `POST /cases/batch` | CAPTURISTA | Hasta 100 casos en una petición; la usa `sincronizacion` (F4). Cada caso recibe el resultado que tendría en `POST /cases` (201, 200 si ya existía, 409 o 422) en `resultados`, en el mismo orden (`indice`) y en su propia transacción: uno rechazado no detiene a los demás. Los catálogos y cada dispositivo se revisan una vez por lote. El límite de D31 cuenta los casos, no la petición, en la misma cuenta que `POST /cases`. Si la base falla, todo el lote es 503 y se reenvía (`local_uuid` evita duplicados). |
| `GET /cases` | CAPTURISTA, EPIDEMIOLOGO, ANALISTA, ADMINISTRADOR | Lista paginada. Filtros: `disease_id`, `region_id` (municipio), `status`, `sex`, `from`, `to` (sobre `report_date`), `page` (1), `per_page` (20, máx. 100). Regresa `casos`, `total`, `pagina`, `por_pagina`, `paginas`. |
| `GET /cases/{id}` | los cuatro roles | Un caso; 404 si no existe. El `ETag` es su versión. |
| `PATCH /cases/{id}` | EPIDEMIOLOGO (cualquier caso pendiente o validado), CAPTURISTA (los suyos, pendientes) | Corrige los campos que vienen en el cuerpo (ver «Corrección y estado»). |
| `POST /cases/{id}/status` | EPIDEMIOLOGO | Valida, descarta, marca duplicado o reabre. |
| `GET /cases/{id}/history` | los cuatro roles | Un cambio por versión, del más viejo al más nuevo. |
| `GET /cases/incomplete` | los cuatro roles (la CAPTURISTA, solo los suyos) | Los casos pendientes o validados a los que les faltan datos, con `faltantes` (D49). |
| `GET /forms` | los cuatro roles (los borradores, solo EPIDEMIOLOGO y ADMINISTRADOR) | Las versiones de los formularios; filtros `disease_id` y `status`. |
| `GET /forms/current` | los cuatro roles | La versión vigente de cada enfermedad (o de una, con `disease_id`): lo que la app guarda para capturar sin red. |
| `GET /forms/{id}` | los cuatro roles | Una versión. |
| `POST /forms` | EPIDEMIOLOGO, ADMINISTRADOR | Crea la versión siguiente de una enfermedad, en borrador. |
| `PUT /forms/{id}` | EPIDEMIOLOGO, ADMINISTRADOR | Reemplaza un borrador; uno publicado o retirado ya no cambia (409). |
| `POST /forms/{id}/publish` | EPIDEMIOLOGO, ADMINISTRADOR | Publica el borrador y retira la versión vigente. |

Los roles siguen la matriz de permisos (`cases.create`, `cases.read`, `cases.update` y
`cases.approve`, migración 010). El monolito deja capturar a cualquier usuario autenticado; aquí
se aplica la matriz.

XML por defecto y JSON con `?format=json` o `Accept: application/json`; los cuerpos se
aceptan en los dos. Errores RFC 7807. XSD del recurso: `docs/contratos/casos/caso.xsd`.

## Cuerpo de `POST /cases`

Obligatorios: `disease_id`, `region_id`, `report_date`. Opcionales: `local_uuid`, `device_id`,
`onset_date`, `age`, `sex` (M/F/O), `latitude` y `longitude` (juntas o ninguna),
`test_result`, `severity`. Un campo desconocido es 422.

`device_id`, si llega, tiene que ser un dispositivo registrado de quien captura (servicio
`dispositivos`): uno que no existe o es de otra cuenta es 422, y uno revocado, 409
`CONFLICTO`, aunque el token siga vigente. Esa revisión no corre en el reintento de un caso
que ya existe: lo que se sincronizó antes de revocar el teléfono se queda.

## Idempotencia (`local_uuid`)

- `local_uuid` nuevo (o ausente, y el servicio genera uno): **201**, `duplicado: false`.
- `local_uuid` que ya existe: **200** con el caso existente y `duplicado: true`. No se valida
  de nuevo, no se escribe y no hay bitácora. Un reintento de la sincronización, o dos
  peticiones simultáneas (`ON CONFLICT DO NOTHING`), nunca duplican.
- `synced_at` se fija al insertar cuando el caso trae `device_id`.

## Corrección y estado (D47)

`seguimiento.py` tiene las reglas; `rutas.py` las aplica dentro de la transacción.

- **Versión:** cada caso nace en la versión 1 y cada cambio la sube en 1. `GET /cases/{id}` la da
  en el `ETag`. Corregir y cambiar el estado piden `If-Match` con la versión que se leyó (con o
  sin comillas): si el caso cambió, **412** `CONFLICTO` con el `ETag` actual y nada se toca; sin
  `If-Match`, **428**. El caso se bloquea (`FOR UPDATE`) mientras se guarda.
- **Corregir (`PATCH`):** solo `disease_id`, `region_id`, `report_date`, `onset_date`, `age`,
  `sex`, `latitude`, `longitude`, `test_result` y `severity`, más `reason` (opcional) y
  `device_id` (si viene de la móvil: uno revocado es 409). Se valida junto con el resto del caso,
  igual que al capturarlo; lo que no se corrige no se vuelve a juzgar contra el catálogo de hoy.
  Si nada cambia, regresa el caso sin subir la versión. Un caso `descartado` o `duplicado` se
  reabre antes (409). El CAPTURISTA solo corrige los suyos y mientras estén pendientes (403).
- **Estado (`POST .../status`):** `pendiente` → `validado`, `descartado` o `duplicado`; `validado` →
  `descartado`, `duplicado` o `pendiente`; `descartado` y `duplicado` → `pendiente`. Otra
  transición es 409. Descartar, duplicado y reabrir piden `reason` (hasta 500 caracteres);
  duplicado, además, `duplicate_of`: el original, que existe, es de la misma enfermedad y no es
  otro duplicado. Reabrir limpia `duplicate_of`.
- **Historial:** cada cambio deja una fila en `case_history` (versión, `correccion` o `estado`,
  quién, cuándo, estado antes y después, `changes` con `{antes, despues}` por campo, motivo y
  dispositivo) y un `UPDATE` en la bitácora.
- **Aviso:** al descartar o marcar duplicado, `notificaciones` avisa a quien capturó el caso
  (`CASE_REJECTED`, best-effort).
- El caso trae además `version`, `updated_at`, `updated_by`, `status_reason` y `duplicate_of`.

## Formularios por enfermedad (D48)

`formularios.py`: la validación de un formulario, la de las respuestas y `case_forms`.

- **Qué es:** los campos fijos del caso no cambian; cada enfermedad suma los suyos. Cada campo
  tiene `clave` (minúsculas, dígitos y `_`; no repite un campo fijo), `etiqueta`, `tipo` (`texto`,
  `entero`, `decimal`, `fecha`, `booleano`, `opcion`, `opciones`), `obligatorio` y, según el tipo,
  `minimo` y `maximo`, `max_largo` (texto, hasta 2000; 500 por omisión) u `opciones`
  (`{valor, etiqueta}`, de 2 a 50), más `ayuda`. De 1 a 60 campos.
- **Versiones:** borrador → publicado → retirado. Lo publicado no cambia; al publicar otra versión la
  anterior se retira, y sigue valiendo para lo capturado con ella sin conexión. A lo más un borrador
  y una publicada por enfermedad (índices únicos en la base).
- **En el caso:** `form_id` (la versión) y `form_answers` (`{clave: valor}`). Las respuestas se
  validan contra esa versión al capturar, en el lote y al corregir: obligatorios, tipos, rangos y
  opciones; un 422 junta todos los motivos. Lo vacío no se guarda y las opciones quedan en el orden
  del formulario. En XML, un número llega como texto y `opciones` como `<item>`: se aceptan igual.
- **Sin formulario:** se acepta, salvo que la versión vigente de la enfermedad tenga `required` en
  true (422 con su `form_id`). Hoy ninguna lo tiene: la app todavía no manda formularios (B4).
- **Corregir:** `PATCH /cases/{id}` acepta `form_answers` (contra la versión del caso) y `form_id`
  (otra versión, con sus respuestas; `null` lo quita). Cambiar la enfermedad de un caso con
  formulario pide el de la nueva o `form_id` null. El cambio queda en el historial.
- Crear, editar y publicar se auditan (`case_forms`).

## Datos incompletos (D49)

A un caso le faltan datos si no trae edad, sexo, inicio de síntomas, resultado, gravedad o ubicación
(`IMPORTANTES` en `rutas.py`; ninguno es obligatorio). Al crear casos así, quien los capturó recibe un
aviso `DATA_INCOMPLETE` con lo que falta: uno por `POST /cases` y uno por lote; un reintento (200) no
avisa. `GET /cases/incomplete` los lista con `faltantes`, para el panel de la app; se completan con
`PATCH /cases/{id}` (D47).

## Variables y base de datos

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL` (rol `svc_casos`: SELECT en `diseases`,
`regions`, `cases` y, desde la migración 031, `id`, `user_id` e `is_revoked` de `devices`;
INSERT en `cases` y `audit_log`; USO de `cases_id_seq`; desde la 057, UPDATE de las columnas
que se corrigen y del seguimiento, y SELECT e INSERT en `case_history`; desde la 059, SELECT,
INSERT y UPDATE en `case_forms` y UPDATE de `form_id` y `form_answers` en `cases`) y
`SERVICIO_NOTIFICACIONES_URL` para el aviso `CASE_REJECTED`.

## Cómo probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD python -m pytest microservicios/casos -q
python -m microservicios.casos.app        # http://127.0.0.1:5221/docs
curl -H "Authorization: Bearer $TOKEN" "http://localhost:5221/api/v1/cases?format=json&per_page=5"
```

Ejemplos de petición y respuesta (JSON y XML): `docs/contratos/casos/ejemplos/`.
