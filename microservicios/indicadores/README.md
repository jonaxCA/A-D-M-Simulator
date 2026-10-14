# EPIDEMIA - Servicio indicadores

Indicadores del tablero y resumen de situación por enfermedad, los mismos del
dashboard del monolito. Solo lectura.

Puerto externo: 5251; puerto interno en Docker: 8000. Contrato en
`docs/contratos/indicadores/openapi.json`.

## Rutas

| Método | Ruta                             | Acceso  | Qué regresa |
|--------|----------------------------------|---------|-------------|
| GET    | `/api/v1/dashboard/indicators`   | Público | Casos activos, tasa de incidencia por 100k, zonas en riesgo y simulaciones activas, con su variación contra la semana previa |
| GET    | `/api/v1/dashboard/situation`    | Público | Casos de la última semana por enfermedad con su tendencia (`estable`, `alerta`, `critico`). `limit` de 1 a 20, por omisión 5 |

Públicas porque el tablero del monolito se ve sin iniciar sesión (`/`).
Usa `get_resumen_indicadores()` y `get_resumen_situacion()` de `backend_web`.

## Caché

`cache:indicadores:indicators` y `cache:indicadores:situation:limit=<n>`, con
TTL de 60 s (`epidemia_comun.cache`). Si Redis está caído, responde directo
de PostgreSQL y la caché se vuelve a llenar sola cuando Redis regresa.

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY` y `REDIS_URL`.

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/indicadores -q
python -m microservicios.indicadores.app
curl "http://127.0.0.1:5251/api/v1/dashboard/indicators?format=json"
curl "http://127.0.0.1:5251/api/v1/dashboard/situation?limit=3"
```

Pendiente: evidencia contra la base real y la entrada en el compose (bloque J).
