# Prueba rápida en vivo del bloque E (E7 y E8)

Fecha: 2026-11-20. Compose de `infra/` (todos los perfiles menos `gpu`) con `curl` directo a los
servicios, MFA apagado (el valor por omisión). Para iniciar sesión se creó una cuenta temporal de
demostración con los roles ADMINISTRADOR, EPIDEMIOLOGO y ANALISTA; al terminar quedó desactivada y sin
roles (la base conserva sus corridas, por la llave foránea). No se guardan tokens ni contraseñas aquí.

La base de la demostración era de una sesión anterior (migraciones hasta la 037); se aplicaron
`038` a `054` con `psql` dentro del contenedor, en orden, y `schema_migrations` quedó en 054 con 45 filas.
Las corridas 1 a 127 son anteriores a MongoDB y no tienen series guardadas; se lanzaron tres nuevas (128 a 130).

| Prueba | Resultado |
|---|---|
| Login (captcha, usuario, contraseña, `dispositivo_id`) con MFA apagado | 200, `access_token` y `refresh_token`; sin `mfa_requerido` |
| `GET /api/v1/runs/130` (`corridas`) | 200 con `priority: "normal"`, `queue_position: null`, `estimated_seconds: null`, `estimate_samples: 0`, `estimate_reason: "La corrida ya terminó."` |
| `POST /api/v1/runs` con `engine: seir-ref`, tres semillas | 202, `priority: "normal"`; las tres terminaron en `completado` en menos de 25 s |
| `POST /api/v1/runs/130/retry` (no hay corridas fallidas) | 409 `CONFLICTO`: «solo se reintenta una fallida». Con el rol EPIDEMIOLOGO solo, 403 |
| `GET /api/v1/runs/130/band` (`resultados`) | 200; cada día trae `p5`, `p50`, `p95` y `corridas: 3` (las que tienen series). Sobre la corrida 127, 404 «La versión no tiene series guardadas» |
| `GET /api/v1/comparisons?runs=129,130` | 200 con `diferencias` (absolutas y relativas contra la de referencia, tasa de ataque, etc.) e `incertidumbre` |
| `GET /api/v1/pareto?runs=129,130` | 200; cada fila lleva `explicacion` (la 130 queda dominada por la 129: «4 menos de fallecimientos con el mismo costo») |
| `GET /api/v1/audit?entity_id=130` (`roles`) | 200, `coincidencias: 4`, eventos con `entidad_id: "130"`; con `entity_id=abc`, 0 resultados |
| `GET /api/v1/sessions/devices` (`sesiones`) | 200, lista con el dispositivo `autorizado` de la cuenta |

Dos observaciones:

- `replicas` en `/band` cuenta las corridas completadas de la versión en PostgreSQL (130), no las que tienen
  series en MongoDB (3, las del campo `corridas` de cada día). Con una base de demostración que ya trae
  corridas viejas, la cifra engaña. No se cambió.
- No hubo corridas fallidas para probar el reintento exitoso: `forzar_error` solo lo honra un ADMINISTRADOR
  y no se quiso dejar fallos en la demostración. El reintento exitoso lo cubren las pruebas de `corridas`.

## MFA encendido

```bash
MFA_PERFILES=ADMINISTRADOR,EPIDEMIOLOGO docker compose -f infra/docker-compose.yml <perfiles> up -d --no-deps --wait auth
# login con la cuenta de demostración
{'mfa_requerido': True, 'mfa_enrolado': False, 'mfa_token': '<oculto>', 'mfa_expira': ...}
# sin la variable, se recrea auth y vuelve a apagado
docker compose -f infra/docker-compose.yml <perfiles> up -d --no-deps --wait auth   # login: access_token, refresh_token, usuario
```

El MFA arranca apagado también en el código (`MFA_PERFILES` sin definir equivale a vacía); ya no depende del compose.

## Pruebas de integración

`python infra/pruebas_integracion.py` (compose aparte, `epidemia-pruebas`, con la demostración abajo):
**137 pasan, 11 se saltan** (GPU y nginx, que piden `--gpu` o `--nginx`), 3 min 22 s. Sin fallas.
