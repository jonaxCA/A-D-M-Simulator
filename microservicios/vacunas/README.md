# EPIDEMIA - Servicio vacunas

Lotes de vacuna que la app móvil lee por QR o código de barras (tabla `vaccine_lots`) y las dosis
que se les aplican. Nunca se aplican más dosis de las que trae un lote, aunque dos teléfonos
apliquen a la vez, ni a un lote caducado.

Puerto externo: 5225; puerto interno en Docker: 8000. Contrato en
`docs/contratos/vacunas/openapi.json`, con un ejemplo JSON y uno XML por ruta en `ejemplos/`.

## Rutas

| Método | Ruta | Roles | Qué hace |
|--------|------|-------|----------|
| POST | `/api/v1/vaccine-lots` | CAPTURISTA, ADMINISTRADOR | Cuerpo `{lot_code, disease_id, doses_total, manufacturer?, region_id?, expires_on?}`. Registra el lote (**201**); si ya estaba con los mismos datos, **200** con el que había |
| GET | `/api/v1/vaccine-lots?lot_code=&disease_id=&region_id=&limit=50` | Los seis perfiles (D42, D56) | Busca lotes, los más recientes primero |
| GET | `/api/v1/vaccine-lots/{lote_id}` | Los seis perfiles | Un lote, con `doses_remaining` y `vencido` |
| POST | `/api/v1/vaccine-lots/{lote_id}/doses` | CAPTURISTA, ADMINISTRADOR | Cuerpo `{doses}`. Descuenta las dosis aplicadas |

El flujo en la app:

1. Escanea el código y lo busca: `GET /api/v1/vaccine-lots?lot_code=<código>`.
2. Si `total` es 0, pide los datos del lote y lo registra. Un reintento con los mismos datos
   responde 200; con otros datos, 409 (alguien ya lo registró distinto: hay que consultarlo).
3. Al vacunar, `POST .../doses` con cuántas dosis se aplicaron.

- `lot_code` es de 1 a 60 caracteres visibles, sin espacios, y es único.
- `vencido` es `true` cuando `expires_on` ya pasó en hora de Monterrey. Un lote caducado se
  registra, pero aplicarle dosis responde 409.
- Aplicar dosis solo descuenta del lote. Ligar un caso a su lote (`cases.vaccine_lot_id`) le
  tocaría a `casos` y todavía no se hace.

| Caso | Respuesta |
|------|-----------|
| Cuerpo, filtro o id inválidos; `doses` de 1 a 1,000 | 422 `DATOS_INVALIDOS` |
| No existe el lote | 404 `NO_ENCONTRADO` |
| `lot_code` ya registrado con otros datos; enfermedad o región inexistentes; no quedan dosis suficientes; lote caducado | 409 `CONFLICTO` |
| Redis caído | 503 `SERVICIO_NO_DISPONIBLE` |

## Cómo funciona

Las reglas de los lotes están en `lotes.py` (antes en `backend_web`, E8), con sus pruebas
contra la base (`tests/test_lotes_bd.py`):

- Aplicar es un solo `UPDATE ... SET doses_used = doses_used + n WHERE doses_used + n <=
  doses_total AND (expires_on IS NULL OR expires_on >= hoy)`: si dos teléfonos aplican a la vez,
  la base ordena los dos y el segundo no pasa si ya no alcanza. `ck_vaccine_lots_usadas` (005)
  es la última defensa.
- El alta y cada aplicación quedan en la bitácora (`CREATE` y `UPDATE` de `doses_used`), en la
  misma transacción.

## Variables

`DATABASE_URL` (rol `svc_vacunas`, migración 033), `JWT_SECRET_KEY`, `REDIS_URL`; opcionales
`JWT_ISSUER` y `JWT_AUDIENCE`.

## Probarlo

```bash
python -m pytest microservicios/vacunas
python -m microservicios.vacunas.app
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5225/api/v1/vaccine-lots?lot_code=FL3239-2026&format=json"
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"doses": 1}' "http://127.0.0.1:5225/api/v1/vaccine-lots/5/doses?format=json"
```

## Campañas (D49)

`campanas.py`, con su propia consulta (`epidemia_comun.bd`); tabla `campaigns` (migración 060).

| Ruta | Roles | Qué hace |
|---|---|---|
| `GET /api/v1/campaigns` | los seis perfiles | De la más reciente a la más vieja; filtros `status`, `disease_id`, `region_id` (las de ese municipio y las de todo el estado) y `limit` |
| `GET /api/v1/campaigns/{id}` | los seis perfiles | Una campaña |
| `POST /api/v1/campaigns` | EPIDEMIOLOGO, ADMINISTRADOR | Crea una; los CAPTURISTA reciben un aviso `CAMPAIGN` |
| `PUT /api/v1/campaigns/{id}` | EPIDEMIOLOGO, ADMINISTRADOR | La edita (se manda todo) |
| `POST /api/v1/campaigns/{id}/cancel` | EPIDEMIOLOGO, ADMINISTRADOR | La cancela con `reason`; aviso `CAMPAIGN` |

- Campos: `name` (hasta 160), `disease_id`, `region_id` (municipio de Nuevo León; null es todo el
  estado), `starts_on` y `ends_on` (no antes de `starts_on` ni de hoy), `target_population` (opcional)
  y `description` (opcional, hasta 2000).
- `status` sale de las fechas: `programada`, `activa`, `terminada`, o `cancelada`. Una cancelada o
  terminada no se edita ni se cancela (409).
- Sin coberturas: eso es el servicio opcional de vacunación. El aviso es best-effort; se audita
  `CREATE` y `UPDATE` de `campaigns`. Necesita `SERVICIO_NOTIFICACIONES_URL`.
