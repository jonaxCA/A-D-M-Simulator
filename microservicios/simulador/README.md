# EPIDEMIA - Servicio simulador

Proceso trabajador: toma corridas de la cola de Redis (`queue:simulaciones`), ejecuta el
motor, guarda el resultado en PostgreSQL y avisa a `notificaciones` al terminar o fallar.
Su única ruta propia es el estado del trabajador.

Puerto externo: 5242; puerto interno en Docker: 8000. Contrato en
`docs/contratos/simulador/openapi.json`.

## Ruta

| Método | Ruta | Roles | Qué regresa |
|--------|------|-------|-------------|
| GET | `/api/v1/worker/status` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR | `trabajador` (nombre del contenedor), `activo`, `corrida_actual`, `procesadas`, `ultima` y `pendientes` en la cola |

Más `/health`, `/docs` y `/openapi.json`, como todos.

## Cómo funciona

`python -m microservicios.simulador` (`__main__.py`) hace tres cosas en un solo proceso:

1. **Al arrancar** cierra como `fallido` las corridas que quedaron en `ejecutando`
   (`simulaciones.recupera_corridas_interrumpidas(estados=("ejecutando",))`). Las que están
   en `encolado` no se tocan: siguen esperando en la cola.
2. **Lanza el hilo trabajador** (`trabajador.ciclo`). Espera en la cola y, por cada corrida,
   llama a `simulaciones.ejecutar_run()`, la misma del monolito:
   - marca `ejecutando` con la transición condicionada, así que dos contenedores nunca corren
     la misma corrida;
   - arma la entrada del motor desde la versión aprobada, corre el motor y guarda el
     resultado y el estado final;
   - audita cada paso.
   El avance (10, 30, 90 y 100) va a `job:<id>:progress` (TTL de 24 h), de donde lo lee
   `corridas`.
3. **Sirve** `/health` y `/api/v1/worker/status` con waitress.

Al terminar, avisa a quien pidió la corrida con `POST /api/v1/notifications` (`RUN_FINISHED`
o `RUN_FAILED`), usando un **token de servicio** (`epidemia_comun.seguridad.token_servicio`).
El aviso es *best-effort*: si `notificaciones` no responde, la corrida ya quedó cerrada y
solo se anota en el log. Si `ejecutar_run` no cerró la corrida (otro trabajador la tomó o se
canceló antes), no se avisa.

Si Redis se cae, el trabajador espera 5 s y vuelve a intentar; un error en una corrida nunca
tumba el hilo.

### Límites conocidos

- **Reinicio con varias réplicas.** Si se reinicia un `simulador` mientras otro está
  corriendo, el que arranca cierra como fallida la corrida del otro. Ese otro descarta su
  resultado (`guardar_resultado_run` ya no la encuentra en `ejecutando`) y la corrida se puede
  volver a lanzar con la misma semilla.
- **PostgreSQL caído al tomar una corrida.** La corrida sale de la cola y se queda
  `encolado` en la base. Se cancela desde `corridas` y se vuelve a lanzar.

## Variables

`DATABASE_URL` (rol `svc_simulador`, migración 029), `JWT_SECRET_KEY`, `REDIS_URL` y
`SERVICIO_NOTIFICACIONES_URL`; opcionales `JWT_ISSUER` y `JWT_AUDIENCE_INTERNA`.

## Probarlo

```bash
python -m pytest microservicios/simulador
pip install waitress   # ya viene en la imagen de Docker
python -m microservicios.simulador 127.0.0.1:5242
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5242/api/v1/worker/status?format=json"
```
