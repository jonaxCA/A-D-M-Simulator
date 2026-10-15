# EPIDEMIA - Servicio series

Curva epidémica y series por edad, sexo y totales, con los filtros de la
pantalla de Monitoreo del monolito. Solo lectura.

Puerto externo: 5252; puerto interno en Docker: 8000. Contrato en
`docs/contratos/series/openapi.json`.

## Rutas

Todas piden `Authorization: Bearer` de cualquier rol con sesión activa, igual
que Monitoreo en el monolito.

| Método | Ruta                            | Qué regresa |
|--------|---------------------------------|-------------|
| GET    | `/api/v1/series/cases`          | Casos por día e incidencia acumulada por 100k |
| GET    | `/api/v1/series/cases/by-age`   | Los seis grupos de edad en orden, aunque alguno venga en cero |
| GET    | `/api/v1/series/cases/by-sex`   | Casos y porcentaje por sexo |
| GET    | `/api/v1/series/cases/totals`   | Casos e incidencia del periodo contra el periodo previo |

Filtros comunes (`epidemia_comun.ambito`):

- `disease_id`: enfermedad; 404 si no existe.
- `region_id`: municipio de Nuevo León; 404 si no existe. Sin él, todo el estado.
- `days`: 7, 30 o 90, por omisión 30. Otro valor es 422.

Cada respuesta repite los filtros aplicados en `filtros`.

## Caché

`cache:series:<ruta>:d=<enfermedad>:r=<municipio>:dias=<n>`, TTL de 60 s. Con
Redis caído, la verificación del token responde 503: es una ruta protegida y
nunca deja pasar.

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY`, `REDIS_URL`; opcionales `JWT_ISSUER` y
`JWT_AUDIENCE`.

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/series -q
python -m microservicios.series.app
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:5252/api/v1/series/cases?days=7&format=json"
```

Pendiente: la entrada en el compose (bloque J). Evidencia de funcionamiento en `evidencias/servicios/series/`.
