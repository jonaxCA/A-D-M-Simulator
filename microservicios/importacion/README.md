# EPIDEMIA - Servicio importacion

Importa series observadas **agregadas** (D53, RF-B08): conteos por periodo y región, nunca
registros por persona (RNF-I05). Revisa la serie y registra su enfermedad, su región, su métrica,
su fuente, su licencia, su corte, su huella SHA-256 y su versión en `observed_datasets` y
`observed_points` (migración 061). Con estas series calibra y valida `calibracion` (D50). La 061
ya trae la de D50: casos confirmados de COVID-19 en Nuevo León por semana de inicio de síntomas,
de la DGE (`datos/observados/covid19_nl_2020_semanal.csv`).

- Puerto externo: 5226. Puerto interno en Docker: 8000. Perfil `vigilancia`.
- Contrato en `docs/contratos/importacion/openapi.json`; el XML de una serie valida contra
  `serie_observada.xsd`. Ejemplos de entrada (CSV, JSON y XML) y de cada respuesta en `ejemplos/`.

## Rutas

| Método | Ruta | Roles | Qué hace |
|--------|------|-------|----------|
| POST | `/api/v1/datasets?code=…&name=…&disease=…&region=…&metric=…&period=…&source=…&license=…&cutoff=…[&url=…]` | EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR (`datasets.upload`) | Revisa e importa. **201** con la versión siguiente de la clave, **200** si ese archivo ya estaba con esa clave, **422** con las primeras fallas |
| POST | `/api/v1/datasets/validate` (los mismos parámetros) | Los mismos | La misma revisión sin guardar: `valido`, la huella, todas las fallas (hasta 50) y el resumen |
| GET | `/api/v1/datasets[?disease=…&region=…]` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR, INVESTIGADOR y AUTORIDAD_SANITARIA (`simulations.read`) | Todas las versiones, de la más nueva a la más vieja (hasta 200) |
| GET | `/api/v1/datasets/{id}` | Los mismos | Metadatos y resumen: puntos, primer y último periodo, total, máximo y periodos en cero |
| GET | `/api/v1/datasets/{id}/points` | Los mismos | Los puntos en orden; en XML, el mismo documento que se importa |

**El archivo** va tal cual en el cuerpo, hasta 2 MB y en UTF-8, y su `Content-Type` dice el formato:
- `text/csv`: líneas `#` opcionales (comentarios), el encabezado `periodo_inicio,valor` y una línea por punto;
- `application/json`: `{"puntos": [{"periodo_inicio": "2020-03-01", "valor": 7}, …]}`;
- `application/xml`: `<serie_observada><puntos><punto><periodo_inicio>…</periodo_inicio><valor>…</valor></punto>…</puntos></serie_observada>`.

**La revisión** (`lectura.py`):
- Solo dos campos por punto: una columna o una clave de más se rechaza (RNF-I05).
- Fechas AAAA-MM-DD y valores enteros no negativos, de 4 a 5000 puntos.
- Periodos seguidos, sin repetirse ni dejar huecos: un periodo sin casos se escribe con 0. Una serie
  por semana tiene todos sus periodos en el mismo día de la semana; las de la DGE van de domingo a
  sábado, como el SINAVE.
- La enfermedad y la región existen, y la región está en el alcance de la cuenta (D43).
- Fuente y licencia obligatorias; el corte no es futuro ni anterior al último periodo.

Un archivo que no se puede leer (no es UTF-8, o el JSON o el XML están rotos) es **400**; otro
`Content-Type`, **415**; más de 2 MB, **413**.

**Versiones (D52):** un conjunto no se edita ni se borra. Importar otra vez la misma clave crea la
versión siguiente, con `CREATE` en la bitácora; el mismo archivo con la misma clave regresa la que
ya estaba, así que el cliente puede reintentar.

## Pruebas

- `tests/test_lectura.py`: los tres formatos y cada falla de la revisión.
- `tests/test_importacion.py`: las rutas con la base simulada, los roles y el alcance.
- `tests/test_importacion_bd.py`: contra la base de pruebas (`DATABASE_URL_PRUEBAS`).
- `tests/test_serie_observada.py`: la 061 sale igual de su script y su serie pasa la revisión.

```bash
python -m pytest microservicios/importacion
```
