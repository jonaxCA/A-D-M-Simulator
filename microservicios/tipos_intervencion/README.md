# EPIDEMIA - Servicio tipos-intervencion

Catálogo de los tipos de intervención con el esquema de sus parámetros
(`param_schema`, JSON Schema) y sus supuestos de efectividad (D58). Las apps arman con él el
formulario de cada intervención. Escribe solo `intervention_effectiveness`; el costo es de
`intervenciones`. Sus reglas viven en `datos.py` (E8: ya no importa `backend_web` y su imagen parte de
`epidemia/base-vigilancia`).

Puerto externo: 5215; puerto interno en Docker: 8000. Contrato en
`docs/contratos/tipos-intervencion/openapi.json`.

> La carpeta se llama `tipos_intervencion` porque Python no importa paquetes con
> guion. El nombre del servicio (en `/health`, en el catálogo y en el contrato)
> es `tipos-intervencion`.

## Rutas

| Método | Ruta                                 | Acceso  | Qué regresa                                       |
|--------|--------------------------------------|---------|---------------------------------------------------|
| GET    | `/api/v1/intervention-types`         | Público | Tipos activos ordenados por nombre, con su esquema |
| GET    | `/api/v1/intervention-types/{code}`  | Público | Un tipo por código (`CIERRE_ESCUELAS`), con su `efectividad`; 404 si no existe o está inactivo |
| GET    | `/api/v1/intervention-types/{code}/effectiveness` | Público | Sus supuestos de efectividad: el general y los de cada enfermedad |
| PUT    | `/api/v1/intervention-types/{code}/effectiveness` | EPIDEMIOLOGO, ADMINISTRADOR | Crea (201) o reemplaza (200) un supuesto: `parametro`, `enfermedad` opcional, `valor`, `min`, `max`, `fuente` y `supuesto`; auditado |

Leer es público, como `regiones`: es un catálogo sin datos personales. Un supuesto no cambia lo que
se simula: cada intervención lleva su propio valor. La 042 trae siete con su fuente (Chu, Polack,
Osterholm, Li y la movilidad de Google en Nuevo León), los derivados marcados como supuesto.

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY` y `REDIS_URL` (los supuestos se guardan con token y sesión
activa).

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/tipos_intervencion -q
python -m microservicios.tipos_intervencion.app
curl "http://127.0.0.1:5215/api/v1/intervention-types"               # XML
curl "http://127.0.0.1:5215/api/v1/intervention-types/CUBREBOCAS?format=json"
```

Corre en `infra/docker-compose.yml`.
