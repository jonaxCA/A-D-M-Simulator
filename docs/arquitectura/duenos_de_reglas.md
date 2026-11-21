# Dueños de las reglas de negocio

> **Estado: Vigente** · 2026-11-20 · E8 (D37). Cada regla vive en un solo servicio; los demás la
> piden por HTTP con `llamar()` y no la reescriben. `epidemia_comun` solo guarda lo técnico
> (verificar tokens, Redis, formatos, errores, llaves). Catálogo: [`microservicios.md`](microservicios.md).

Estado: **movida** = ya vive con su dueño y no queda copia en `epidemia_comun` ni en otro
servicio; **copia** = existe más de una y hay que dejar una; **pendiente** = la mueve el bloque
indicado.

## Bloque E: identidad y simulación

| Regla de negocio | Servicio dueño | Dónde vive | Bloque | Estado |
|---|---|---|---|---|
| Credenciales, captcha, bloqueo por intentos fallidos, emisión del *access* | `auth` | `auth/datos.py`, `auth/rutas.py` | E | movida |
| MFA: TOTP, códigos de respaldo, restablecer (D40) | `auth` | `auth/mfa.py` | E | movida |
| Abrir sesión, TTL de 8 h y tope de sesiones concurrentes (D41) | `sesiones` | `sesiones/almacen.py`, `POST /api/v1/sessions/internal/open` | E | movida (`auth` la llama por HTTP) |
| Renovar con rotación de *refresh* y detectar su reutilización | `sesiones` | `sesiones/almacen.py` | E | movida |
| Cerrar sesiones (logout, de una cuenta, de un dispositivo) y revocar tokens | `sesiones` | `sesiones/almacen.py`; `usuarios` y `roles` piden `DELETE /sessions/user/{id}` con `epidemia_comun.sesiones.cerrar_de_usuario` | E | movida |
| Dispositivos autorizados de una cuenta (D41) | `sesiones` | `sesiones/dispositivos.py` | E | movida |
| Revisar que un token siga vigente (firma, revocación, sesión abierta) | todos (técnico) | `epidemia_comun/seguridad.py`, `epidemia_comun/sesiones.verificar` | E | se queda en `epidemia_comun` |
| Altas, ediciones y bajas de cuentas; perfil; instituciones (D42) | `usuarios` | `usuarios/datos.py`, `usuarios/rutas.py` | E | movida |
| Roles, permisos y asignación de rol | `roles` | `roles/rutas.py` | E | movida |
| Alcance por región e institución (D43) | `roles` (dueño); los demás lo piden | `roles/rutas.py`, cliente en `epidemia_comun/alcance.py` | E | movida |
| Bitácora: consulta, resumen e historial | `roles` | `roles/rutas.py` | E | movida |
| Lanzar, cancelar y reintentar corridas; prioridad, candado y cola (D44) | `corridas` | `corridas/datos.py`, `corridas/rutas.py` | E | movida |
| Estimación y posición en la cola | `corridas` | `corridas/datos.py` (`estimar_corrida`) | E | movida |
| Ejecutar la corrida, avance, recuperación de interrumpidas (D38) y escribir resultados | `simulador` | `simulador/ejecucion.py`, `trabajador.py`, `datos.py` | E | movida |
| Curvas diarias de una corrida (MongoDB, D28) | `simulador` escribe, `resultados` lee | `simulador/serie.py`, `resultados/serie.py` | E | movida (ya no está en `epidemia_comun`) |
| Resultados, indicadores y banda p5-p95 (D8) | `resultados` | `resultados/rutas.py` | E | movida |
| Comparar corridas: diferencias, incertidumbre y contrafactual | `comparacion` | `comparacion/rutas.py` | E | movida |
| Costo-impacto, frontera de Pareto y sensibilidad | `pareto` | `pareto/dominio.py`, `pareto/rutas.py` | E | movida |
| Elegir hasta N corridas a comparar (`corridas_a_comparar`) | `comparacion` y `pareto` | `comparacion/seleccion.py` y `pareto/seleccion.py` (una copia en cada uno, D36) | E | movida |

## Compartidas o con copia

| Regla de negocio | Servicio dueño | Dónde vive | Bloque | Estado |
|---|---|---|---|---|
| Armar la entrada del motor desde una versión (`entrada_de_version`) | `simulador` (la usa `pareto` para el costo-impacto) | `procesamiento/entrada_motor.py` (se importa, D37) | E | movida a `procesamiento`; no es de ningún servicio |
| `get_run` (corrida con su versión, escenario y región) | `corridas` | `corridas/datos.py`; copias en `resultados/datos.py`, `simulador/datos.py` y `pareto/datos.py` | E | copia: las lecturas de solo consulta quedan, la regla es de `corridas` |
| `_sincroniza_lote` (estado del lote según sus corridas) | `simulador` | `simulador/datos.py`; copia en `corridas/datos.py` (cancelar y reintentar) | E | copia: pendiente dejar una |
| `region_de_version` (para el alcance) | `corridas` | `corridas/datos.py`; copia en `pareto/datos.py` | E | copia |
| Monolito `backend_web` (`queries.py`, `simulaciones.py`) | los de arriba | `backend_web/` | C | se retira cuando la web consuma los servicios (D36, E9) |

## Pendientes de D y F

| Regla de negocio | Servicio dueño | Dónde vive hoy | Bloque | Estado |
|---|---|---|---|---|
| Rangos de los parámetros epidemiológicos (`parametros_epidemiologicos`) | `parametros` | `epidemia_comun/validaciones.py` | D | pendiente |
| Filtros y clave de ámbito de las consultas analíticas (`filtros_ambito`, `clave_ambito`) | `series`, `zonas` | `epidemia_comun/ambito.py` | F | pendiente |

## Contratos de dominio

Cada respuesta se arma con los campos que dice el contrato (`docs/contratos/<servicio>/`), no con
la fila de la base ni con un objeto interno. Cuando una consulta trae más columnas de las que se
publican (por ejemplo `region_population` en `get_run`), la ruta las recorta con
`epidemia_comun.contratos.proyectar(fila, CAMPOS)`; `corridas` lo hace así y una prueba compara
las claves con el ejemplo del contrato. Las demás respuestas de E se arman con diccionarios
explícitos.
