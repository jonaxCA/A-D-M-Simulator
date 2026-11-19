# EPIDEMIA - Servicio simulador

Proceso trabajador: toma las corridas de su motor de su cola de Redis
(`queue:simulaciones:<motor>`), ejecuta el motor, guarda el resumen en `simulation_runs` y la
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
| GET | `/api/v1/worker/status` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR | `trabajador` (nombre del contenedor), `motor`, `activo`, `corrida_actual`, `procesadas`, `ultima` y `pendientes` en la cola de su motor |

Más `/health`, `/docs` y `/openapi.json`, como todos.

## Cómo funciona

`python -m microservicios.simulador` (`__main__.py`) hace tres cosas en un solo proceso:

1. **Al arrancar** cierra como `fallido` las corridas de su motor que quedaron en
   `ejecutando` (`simulaciones.recupera_corridas_interrumpidas(estados=("ejecutando",),
   engine=MOTOR)`) y vuelve a meter a su cola las que están `encolado` en PostgreSQL, en orden
   de id y sin repetir las que ya estén en la cola (D19). Las de otro motor las atiende su
   propio simulador. Si Redis no responde, el arranque no falla: el ciclo reintenta. La
   corrida reencolada pierde `forzar_error` (no se guarda en la base).
2. **Lanza el hilo trabajador** (`trabajador.ciclo`). Espera en la cola y, por cada corrida,
   llama a `simulaciones.ejecutar_run()`, la misma del monolito:
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
3. **Sirve** `/health` y `/api/v1/worker/status` con waitress.

Al terminar, avisa a quien pidió la corrida con `POST /api/v1/notifications` (`RUN_FINISHED`
o `RUN_FAILED`), usando un **token de servicio** (`epidemia_comun.seguridad.token_servicio`).
El aviso es *best-effort*: si `notificaciones` no responde, la corrida ya quedó cerrada y
solo se anota en el log. Si `ejecutar_run` no cerró la corrida (otro trabajador la tomó o se
canceló antes), no se avisa.

Si Redis se cae, el trabajador espera 5 s y vuelve a intentar; un error en una corrida nunca
tumba el hilo.

La serie va antes que la confirmación para que una corrida `completado` no se quede sin curvas
si el proceso muere entre los dos pasos. Si muere ahí, la corrida se queda `ejecutando` con su
serie en MongoDB; `resultados` no la sirve (409, no está completada) y, al arrancar de nuevo, el
simulador la cierra como `fallido` (paso 1). Volver a lanzarla crea otra corrida, con su propio
`run_id`, así que no se duplica nada.

Si MongoDB no responde, la corrida se confirma igual, con su resumen en PostgreSQL y su aviso
(RNF-C08). La serie queda en `series_pendientes` y el ciclo la reintenta cada 30 s; guardar
reemplaza por `{run_id, dia}`, así que un reintento no duplica días. Mientras tanto,
`resultados` responde 404 a sus curvas.

### Límites conocidos

- **Reinicio con varias réplicas.** Si se reinicia un `simulador` mientras otro está
  corriendo, el que arranca cierra como fallida la corrida del otro. Ese otro descarta su
  resultado y su serie (`guardar_resultado_run` ya no la encuentra en `ejecutando`) y la
  corrida se puede volver a lanzar con la misma semilla.
- **PostgreSQL caído al tomar una corrida.** La corrida sale de la cola y se queda
  `encolado` en la base. Se cancela desde `corridas` y se vuelve a lanzar.
- **MongoDB caído y reinicio después de confirmar.** Las series pendientes viven en la memoria
  del proceso. Si se reinicia antes de que vuelva MongoDB, se pierden: la corrida queda
  `completado` con su resumen, pero sin serie (`resultados` responde 404 a sus curvas). No hay
  una reconciliación automática. La misma versión con la misma semilla da la misma serie, así
  que se puede regenerar volviendo a lanzarla.
- **Serie de una corrida que no se completó.** La de una corrida interrumpida entre guardar
  la serie y confirmarla se queda en MongoDB cuando el arranque la cierra como `fallido`. Lo
  mismo si el `UPDATE` que confirma truena: la corrida queda `fallido` y su serie no se borra,
  porque con la conexión caída no se sabe si el `UPDATE` alcanzó a aplicarse. `resultados` no
  la sirve, pero `series_corridas.banda()` no filtra por estado y la contaría.
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
