# EPIDEMIA - Servicio simulador

Proceso trabajador: toma las corridas de su motor de sus colas de Redis
(`queue:simulaciones:<motor>`, `:alta` y `:baja`; primero las altas, D44), ejecuta el motor, guarda el resumen en `simulation_runs` y la
serie diaria en MongoDB (`series_corridas`, D28), y avisa a `notificaciones` al terminar o
fallar. Su única ruta propia es el estado del trabajador.

Hay un contenedor por motor (D2). `SIMULADOR_MOTOR` dice cuál: `seir-ref` si no viene,
`abm-ref` o `abm-gpu`. Un motor que no se puede correr en el contenedor (`abm-gpu` sin
`pyflamegpu` o sin GPU) detiene el arranque, para no tomar corridas que no puede correr. El
compose trae tres:

- `simulador` (`seir-ref`, puerto 5242);
- `simulador-abm` (`abm-ref`, sin puerto publicado);
- `simulador-gpu` (`abm-gpu`, sin puerto publicado), con su propia imagen (`gpu.Dockerfile`) y
  en el perfil `gpu`, porque necesita una GPU de NVIDIA y NVIDIA Container Toolkit en el host
  (`procesamiento/abm_gpu/README.md`).

Así una corrida larga del ABM no detiene las del SEIR, y uno sin GPU nunca toma una de
`abm-gpu`. Los motores implementados están en `procesamiento/motores.py`.

Puerto externo: 5242; puerto interno en Docker: 8000. Contrato en
`docs/contratos/simulador/openapi.json`.

## Ruta

| Método | Ruta | Roles | Qué regresa |
|--------|------|-------|-------------|
| GET | `/api/v1/worker/status` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR | `trabajador` (nombre del contenedor), `motor`, `activo`, `corrida_actual`, `procesadas`, `ultima` y `pendientes` en las colas de su motor |

Más `/health`, `/docs` y `/openapi.json`, como todos.

## Cómo funciona

`python -m microservicios.simulador` (`__main__.py`) hace cuatro cosas en un solo proceso:

1. **Al arrancar** regresa a `encolado` las corridas de su motor que quedaron en `ejecutando`
   (D38, `ejecucion.reencola_corridas_interrumpidas`), si tienen menos de 3 intentos
   (`attempts`, migración 045) y la versión de motor es la que corre ahora. Las demás las
   cierra como `fallido` y borra su serie. Luego vuelve a meter a su cola las que están
   `encolado` en PostgreSQL, en orden de id, cada una en la cola de su prioridad y sin repetir las que ya estén en la cola (D19). Las de otro motor las atiende su
   propio simulador. Si Redis no responde, el arranque no falla: el ciclo reintenta. La
   corrida reencolada pierde `forzar_error` (no se guarda en la base).
2. **Lanza el hilo trabajador** (`trabajador.ciclo`). Espera en la cola y, por cada corrida,
   llama a `ejecucion.ejecutar_run()` (SQL en `datos.py`; ya no importa `backend_web`, E8):
   - marca `ejecutando` con la transición condicionada, así que dos contenedores nunca corren
     la misma corrida;
   - arma la entrada del motor desde la versión aprobada y corre el motor;
   - llama a `guardar_serie`, donde el trabajador guarda la serie en `series_corridas`: un
     documento por día (ver `epidemia_comun/README.md`, «MongoDB»);
   - después confirma la corrida con su resumen, huella y trazabilidad en `simulation_runs`,
     en un solo `UPDATE` que solo aplica si sigue `ejecutando`. Si ya no lo estaba (otro
     proceso la cerró), descarta el resultado y llama a `descartar_serie`, que borra la serie
     de MongoDB y de `series_pendientes`;
   - audita cada paso.
   El avance (10, 30, 90 y 100) va a `job:<id>:progress` (TTL de 24 h), de donde lo lee
   `corridas`.
3. **Lanza el hilo del latido** (`trabajador.latir`, F7). Cada 10 s, mientras el trabajador
   corre, escribe `worker:<motor>:<nombre del contenedor>` con su corrida actual y cuántas lleva,
   con TTL de 30 s. `estado-servicios` los cuenta por motor en `/api/v1/services/capacity`: un
   simulador muerto, o uno cuyo hilo trabajador terminó, deja de contar como vivo a los 30 s.
   Va en otro hilo porque durante una corrida larga el ciclo no vuelve a la cola. Con Redis
   caído no hay latido (tampoco toma corridas).
4. **Sirve** `/health` y `/api/v1/worker/status` con waitress.

Al terminar, avisa a quien pidió la corrida con `POST /api/v1/notifications` (`RUN_FINISHED`
o `RUN_FAILED`), usando un **token de servicio** (`epidemia_comun.seguridad.token_servicio`).
El aviso es *best-effort*: si `notificaciones` no responde, la corrida ya quedó cerrada y
solo se anota en el log. Si `ejecutar_run` no cerró la corrida (otro trabajador la tomó o se
canceló antes), no se avisa.

Si Redis se cae, el trabajador espera 5 s y vuelve a intentar; un error en una corrida nunca
tumba el hilo.

La serie va antes que la confirmación para que una corrida `completado` no se quede sin curvas
si el proceso muere entre los dos pasos. Si muere ahí [Retro: «Fallo de worker»]:
- La corrida se queda `ejecutando` con su serie en MongoDB, y `resultados` no la sirve (409, no
  está completada).
- Al arrancar de nuevo, el simulador la reencola (paso 1) y la repite **con el mismo `run_id`
  y la misma semilla**. La serie se reescribe por `{run_id, dia}` y la corrida se confirma.
- Resultado: una sola corrida, `completado`, con su serie entera; ni corridas ni días
  duplicados. Lo prueba `test_f5_el_trabajador_muere_entre_guardar_la_serie_y_confirmar`.
- A los 3 intentos se cierra como `fallido` y su serie se borra.

Si MongoDB no responde, la corrida se confirma igual, con su resumen en PostgreSQL y su aviso
(RNF-C08). La serie queda en `series_pendientes` y el ciclo la reintenta cada 30 s; guardar
reemplaza por `{run_id, dia}`, así que un reintento no duplica días. Mientras tanto,
`resultados` responde 404 a sus curvas.

**Serie perdida después de confirmar (D38).** Si el proceso muere con la serie aún en
`series_pendientes`, la corrida queda `completado` sin curvas. Al arrancar, el ciclo busca las
`completado` de su motor que no tienen serie en `series_corridas` (`trabajador.conciliar`) y la
regenera con la misma semilla. Solo la guarda si `engine_version`, `scenario_checksum` y el
resumen regenerados son iguales a los guardados en `simulation_runs`; si alguno difiere, lo
registra y no escribe nada. Con MongoDB caído lo reintenta cada 30 s, y es un solo barrido por
arranque. Lo prueban `test_conciliar_*` y
`test_f5_la_serie_pendiente_se_pierde_con_el_proceso_y_el_arranque_la_regenera`.

### Límites conocidos

- **Reinicio con varias réplicas.** Si se reinicia un `simulador` mientras otro del mismo
  motor está corriendo, el que arranca reencola la corrida del otro. El otro no la puede
  confirmar (`guardar_resultado_run` ya no la encuentra en `ejecutando`) y descarta su
  resultado; la corrida se repite con la misma semilla y da lo mismo.
- **PostgreSQL caído al tomar una corrida.** La corrida sale de la cola y se queda
  `encolado` en la base. Se cancela desde `corridas` y se vuelve a lanzar.
- **Serie regenerada que no coincide.** Si cambió la versión del motor, la huella del escenario
  o el resumen, la serie no se regenera y la corrida queda `completado` sin curvas: se avisa en
  el registro y hay que volver a lanzar la corrida.
- **Serie de una corrida que no se completó.** Si el `UPDATE` que confirma truena, la corrida
  queda `fallido` y su serie no se borra, porque con la conexión caída no se sabe si el `UPDATE`
  alcanzó a aplicarse. `resultados` no la sirve, y `series_corridas.banda()` la ignora si quien
  la llama le pasa `run_ids` con las corridas completadas (D38).
- **Corridas encoladas antes de la cola por motor.** Hasta octubre de 2026 la cola era
  `queue:simulaciones`, sin motor. Si al actualizar quedó algo ahí, nadie lo toma: esas
  corridas siguen `encolado`; se cancelan desde `corridas` y se vuelven a lanzar con la misma
  semilla.

## Variables

`DATABASE_URL` (rol `svc_simulador`, migraciones 029 y 038), `JWT_SECRET_KEY`, `REDIS_URL`,
`MONGO_URL` y `SERVICIO_NOTIFICACIONES_URL`; opcionales `JWT_ISSUER`, `JWT_AUDIENCE_INTERNA` y
`MONGO_TIMEOUT_MS`.

## Probarlo

```bash
python -m pytest microservicios/simulador
pip install waitress   # ya viene en la imagen de Docker
python -m microservicios.simulador 127.0.0.1:5242
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5242/api/v1/worker/status?format=json"
```
