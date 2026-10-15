# EPIDEMIA - Servicio tipos-intervencion

Catálogo de los tipos de intervención con el esquema de sus parámetros
(`param_schema`, JSON Schema). Las apps arman con él el formulario de cada
intervención. Solo lectura: no escribe ninguna tabla.

Puerto externo: 5215; puerto interno en Docker: 8000. Contrato en
`docs/contratos/tipos-intervencion/openapi.json`.

> La carpeta se llama `tipos_intervencion` porque Python no importa paquetes con
> guion. El nombre del servicio (en `/health`, en el catálogo y en el contrato)
> es `tipos-intervencion`.

## Rutas

| Método | Ruta                                 | Acceso  | Qué regresa                                       |
|--------|--------------------------------------|---------|---------------------------------------------------|
| GET    | `/api/v1/intervention-types`         | Público | Tipos activos ordenados por nombre, con su esquema |
| GET    | `/api/v1/intervention-types/{code}`  | Público | Un tipo por código (`CIERRE_ESCUELAS`); 404 si no existe o está inactivo |

Públicas, como `regiones`: es un catálogo sin datos personales. Lee
`intervention_types` con `queries.get_tipos_intervencion()`.

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY` y `REDIS_URL` (la biblioteca no arranca sin
ellas aunque este servicio no use tokens).

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/tipos_intervencion -q
python -m microservicios.tipos_intervencion.app
curl "http://127.0.0.1:5215/api/v1/intervention-types"               # XML
curl "http://127.0.0.1:5215/api/v1/intervention-types/CUBREBOCAS?format=json"
```

Pendiente: la entrada en el compose (bloque J). Evidencia de funcionamiento en `evidencias/servicios/tipos-intervencion/`.
