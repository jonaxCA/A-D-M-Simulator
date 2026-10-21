# EPIDEMIA - Servicio resultados

Curvas e indicadores de una corrida completada, tal como los guardó el `simulador`. Solo
lectura. Cada respuesta lleva el aviso de que los resultados no son una predicción
(`AVISO_SIMULACION`).

Puerto externo: 5243; puerto interno en Docker: 8000. Contrato en
`docs/contratos/resultados/openapi.json`. El XML de `/results` valida contra
`docs/contratos/resultados/resultado.xsd`.

## Rutas

| Método | Ruta | Qué regresa |
|--------|------|-------------|
| GET | `/api/v1/runs/{run_id}/results` | `aviso`, `simplificaciones` del modelo, `corrida` (escenario, versión, semilla, población, horizonte), `engine_version`, `scenario_checksum`, `resumen`, `serie` y `trazabilidad` de los parámetros |
| GET | `/api/v1/runs/{run_id}/curves` | `aviso`, `run_id` y `serie`: un punto por día |
| GET | `/api/v1/runs/{run_id}/indicators` | `aviso`, `run_id` y `resumen`, con el desglose por grupo de edad |

Las tres piden ANALISTA, EPIDEMIOLOGO o ADMINISTRADOR, los roles de la pantalla de detalle de
una corrida del monolito. CAPTURISTA recibe 403.

| Caso | Respuesta |
|------|-----------|
| Id inválido | 422 `DATOS_INVALIDOS` |
| No existe la corrida o no tiene resultado guardado | 404 `NO_ENCONTRADO` |
| La corrida no está completada | 409 `CONFLICTO`, con su estado en `detail` |

En XML, cada día de la serie es un `<punto>`, cada grupo de edad un `<grupo_edad>` y cada
parámetro de la trazabilidad un `<parametro>`.

## Caché

El resultado de una corrida completada ya no cambia: se guarda 300 s en
`cache:resultados:run=<id>`. Las tres rutas comparten esa entrada. Lo que no está completado
no entra a la caché. Si Redis se cae, las rutas responden 503 porque el token no se puede
verificar.

## Variables

`DATABASE_URL` (rol `svc_resultados`, migración 029), `JWT_SECRET_KEY`, `REDIS_URL`;
opcionales `JWT_ISSUER` y `JWT_AUDIENCE`.

## Probarlo

```bash
python -m pytest microservicios/resultados
python -m microservicios.resultados.app
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5243/api/v1/runs/42/indicators?format=json"
```
