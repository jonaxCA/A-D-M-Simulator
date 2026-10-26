# EPIDEMIA - Servicio casos

Puerto externo 5221; puerto interno en Docker, 8000. Registra y consulta casos
epidemiológicos (tabla `cases`). Es el único servicio que escribe en ella.

## Rutas (`/api/v1`)

| Ruta | Roles | Qué hace |
|---|---|---|
| `POST /cases` | CAPTURISTA, ADMINISTRADOR | Valida con `queries.valida_caso` (catálogo vigente de enfermedades y municipios, fechas, rangos, coordenadas completas), inserta con `status = pendiente` y deja un `CREATE` en `audit_log`, en la misma transacción. `reported_by` sale del token. |
| `GET /cases` | CAPTURISTA, EPIDEMIOLOGO, ANALISTA, ADMINISTRADOR | Lista paginada. Filtros: `disease_id`, `region_id` (municipio), `status`, `sex`, `from`, `to` (sobre `report_date`), `page` (1), `per_page` (20, máx. 100). Regresa `casos`, `total`, `pagina`, `por_pagina`, `paginas`. |
| `GET /cases/{id}` | los cuatro roles | Un caso; 404 si no existe. |

Los roles siguen la matriz de permisos (`cases.create`, `cases.read`, migración 010). El
monolito deja capturar a cualquier usuario autenticado; aquí se aplica la matriz.

XML por defecto y JSON con `?format=json` o `Accept: application/json`; los cuerpos se
aceptan en los dos. Errores RFC 7807. XSD del recurso: `docs/contratos/casos/caso.xsd`.

## Cuerpo de `POST /cases`

Obligatorios: `disease_id`, `region_id`, `report_date`. Opcionales: `local_uuid`, `device_id`,
`onset_date`, `age`, `sex` (M/F/O), `latitude` y `longitude` (juntas o ninguna),
`test_result`, `severity`. Un campo desconocido es 422.

## Idempotencia (`local_uuid`)

- `local_uuid` nuevo (o ausente, y el servicio genera uno): **201**, `duplicado: false`.
- `local_uuid` que ya existe: **200** con el caso existente y `duplicado: true`. No se valida
  de nuevo, no se escribe y no hay bitácora. Un reintento de la sincronización, o dos
  peticiones simultáneas (`ON CONFLICT DO NOTHING`), nunca duplican.
- `synced_at` se fija al insertar cuando el caso trae `device_id`.

## Variables y base de datos

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL` (rol `svc_casos`: SELECT en `diseases`,
`regions`, `cases`; INSERT en `cases` y `audit_log`; USO de `cases_id_seq`).

## Cómo probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD python -m pytest microservicios/casos -q
python -m microservicios.casos.app        # http://127.0.0.1:5221/docs
curl -H "Authorization: Bearer $TOKEN" "http://localhost:5221/api/v1/cases?format=json&per_page=5"
```

Ejemplos de petición y respuesta (JSON y XML): `docs/contratos/casos/ejemplos/`.
