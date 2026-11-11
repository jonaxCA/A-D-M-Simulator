## Decisiones en Pendiente

Nadie ha decidido estas (ver `decisiones.md`):

- [D24](D24-calibracion-del-abm.md): calibración y parámetros de los agentes. Depende de D22.
- [D28](D28-uso-de-mongodb.md): qué datos van a MongoDB. Depende de D21.
- [D29](D29-volumen-de-datos.md): volumen de datos de alto volumen. Depende de D6, D8 y D28.

## Decisiones por confirmar con el equipo (ya están registradas, ver `decisiones.md`):

- D17, D18 y D20 quedaron aceptadas el 2026-11-08 (ver `decisiones.md`). D19 (Redis sin datos autoritativos) sigue por confirmar.
- D25 quedó aceptada el 2026-11-08 (ver `decisiones.md`). Sus cambios están en «Cambios pendientes por D25».
- D27 quedó aceptada el 2026-11-08 con los tres servicios implementados en `desarrollo-movil`, que ya está integrada en esta rama (ver «Cambios pendientes por D27»).
- Las del antiguo punto 5 y 6 ya eran D9, D11 y D12.
- El antiguo punto 7 (FLAME GPU con el motor de Python como respaldo) quedó en D23.

## Cambios pendientes por D27

D27 quedó aceptada el 2026-11-08 (ver [`D27-servicios-nuevos-para-la-movil.md`](D27-servicios-nuevos-para-la-movil.md)). Los tres servicios se implementaron en la rama `desarrollo-movil`, que se integró en esta el 2026-11-08 (ba66738). Lo de abajo ya está hecho.

### Código

- **Hecho. Integración de `desarrollo-movil`:** trajo `microservicios/dispositivos`, `evidencias` y `vacunas`, sus entradas en `infra/docker-compose.yml`, las migraciones 031 a 033 y sus pruebas.

### Documentos

- **Hecho. Contratos:** `docs/contratos/dispositivos`, `evidencias` y `vacunas` llegaron con la integración.
- **Catálogo:** `docs/arquitectura/microservicios.md` ya lista los tres. No cambia.

### Preguntas abiertas

- ¿Se actualiza «hoy, el 031» en `propuesta_correcciones_primer_parcial.md` (línea 52)? Es la propuesta ya respondida; no la toqué.

## Cambios pendientes por D1

D1 quedó aceptada el 2026-11-07 (ver [`D01-permisos-y-auditoria.md`](D01-permisos-y-auditoria.md)). Estos cambios no están implementados; se hacen cuando el equipo lo pida.

### Código

- **Migración 034** (siguiente número libre; 031 a 033 son de D27 y no se edita la 010): crear `scenarios.approve`, darlo a EPIDEMIOLOGO y ADMINISTRADOR, y quitar `audit.read` al EPIDEMIOLOGO.
- **Quitar la captura de casos de la web:** la ruta `/reportes/nuevo`, sus enlaces y su plantilla. `cases.create` sigue para el CAPTURISTA, en la app móvil y en la API.
- **Candados por permiso** (propuesta, pasos 4 a 7): leer los permisos al iniciar sesión y guardarlos en el JWT (`perms`) en `backend_web/auth.py`; crear `requiere_permiso(codigo)` en `frontend_web/app/permisos.py`, que responde 403 y registra `PERMISSION_DENIED` con `log_audit`; cambiar el candado de cada ruta según la tabla de la propuesta; exponer `puede()` a las plantillas.
- **Cuenta de prueba de CAPTURISTA** (propuesta, paso 8) en `datos/postgres/semillas/demo_datos_nl.sql`. Sirve para la API, no para la web.
- **Verificación:** `grep -n "roles_required\|admin_required" frontend_web/app/routes.py` no regresa nada.

### Documentos

- `requerimentos/matriz-permisos.md`: «Aprobar / rechazar escenario» pasa a Admin ✓ (hoy dice —). El encabezado «Estado: por confirmar» debe actualizarse con esta decisión.

### Preguntas abiertas

- ¿El ADMINISTRADOR también captura casos? La respuesta 1 dice solo CAPTURISTA. La matriz le quita la captura, pero la migración 010 le da todos los permisos, incluido `cases.create`.
- ¿El login web rechaza al CAPTURISTA, o le deja entrar y le niega cada pantalla con 403?

### Efectos en otras decisiones

- D4 ya se tomó; ver «Cambios pendientes por D4».

## Cambios pendientes por D4

D4 quedó aceptada el 2026-11-07 (ver [`D04-web-contra-escritorio.md`](D04-web-contra-escritorio.md)). La parte del escritorio ya está hecha y la de la web se hizo el 2026-11-11, a petición del equipo.

### Código

- **Hecho. Web, creación de escenarios:** quitar `/escenarios/nuevo`, `/escenarios/<id>/versiones/nueva`, `/escenarios/<id>/duplicar`, las rutas de intervenciones (`/escenarios/<id>/intervenciones`, con agregar, quitar y mover) y `/escenarios/<id>/enviar`. La web conserva `/escenarios/<id>/revisar` y `/revisiones`.
- **Hecho. Web, corridas:** quitar `/simulaciones/<id>/ejecutar` y `/simulaciones/corridas/<id>/reejecutar`. Lanzar una corrida pasa a escritorio. Con eso, `frontend_web/run.py` ya no cierra corridas al arrancar.
- **Hecho. Web, consulta:** `/escenarios`, `/escenarios/<id>`, `/simulaciones` y `/simulaciones/corridas/<id>` se quedan en solo lectura. Sus plantillas ya no tienen botones de editar o lanzar; un escenario en borrador avisa que se edita en el escritorio.
- **Hecho. Web, comparación:** la vista `/comparacion` se queda como consulta. No se le agrega exportación ni impresión, porque van en escritorio.
- **Escritorio:** hecho en el MVP de `frontend_desktop/`. Crea escenarios y versiones, duplica, edita intervenciones y envía a revisión. También lanza lotes de corridas y compara los resultados, con exportación e impresión.

### Documentos

- **Arquitectura v3:** escribir el reparto. La fila C5 de `arquitectura/brechas_v3.md` ya se actualizó el 2026-11-09.

### Preguntas abiertas

- ~~¿`/comparacion/costos` es consulta o edición? La tabla no la menciona.~~ Es edición, pero del catálogo: fija el costo unitario de los tipos de intervención (EPIDEMIOLOGO y ADMINISTRADOR), que el escritorio no hace. Se queda en la web.

## Cambios pendientes por D2

D2 quedó aceptada el 2026-11-08 (ver [`D02-papel-del-seir.md`](D02-papel-del-seir.md)). Estos cambios no están implementados.

### Código

- **Nombre del motor:** cambiar `ENGINE_VERSION` de `python-ref-0.1` a `seir-ref-0.1` en `procesamiento/motor/modelo.py`.
- **Migración de motores** (siguiente número libre). Hoy sería la 034, pero D1 también la reserva: si la de D1 va primero, esta es la 035. El CHECK de `simulation_batches.engine` (014) acepta `python-ref`, `numba` y `cuda`. Hay que cambiarlo a `seir-ref`, `abm-ref` y `abm-gpu`, y el orden dentro de la migración es: soltar el CHECK, convertir los valores, poner el CHECK nuevo y cambiar el DEFAULT.
- **ABM en Python** como paquete aparte en `procesamiento/`, con la misma entrada y salida que el SEIR. Fuera del segundo parcial según `AGENTS.md` (el ABM está fuera de alcance) y D21: pasa al tercero, salvo que el equipo diga otra cosa.

### Documentos

- **Contrato del motor** en `docs/contratos/`: el formato de entrada y salida que deben respetar los tres motores.

## Cambios pendientes por D23

D23 quedó aceptada el 2026-11-08 (ver [`D23-tecnologia-del-abm.md`](D23-tecnologia-del-abm.md)). Estos cambios no están implementados.

### Código e infraestructura

- **Imagen de `simulador`:** definir una imagen con soporte para CUDA, porque FLAME GPU lo necesita.
- **Máquina de Compute Engine con GPU:** elegir el tipo de máquina y su GPU.

### Costos

- Estimar el costo de la máquina con GPU (horas encendidas) y compararlo con los créditos: 100 USD por integrante, unos 600 USD en total si somos seis, como dice `AGENTS.md`. Registrar el resultado en D23.

### Fuera del segundo parcial

- CUDA y FLAME GPU están fuera de alcance del segundo parcial (`AGENTS.md`). Su implementación pasa al tercero (D21).

## Cambios pendientes por D3

D3 quedó aceptada el 2026-11-08 (ver [`D03-unidad-de-costo.md`](D03-unidad-de-costo.md)). Estos cambios no están implementados.

### Código

1. **Trazabilidad fuera del motor:** mover `_desempaca`, `_es_numero` y `_estado_traza` de `motor/parametros.py` a `procesamiento/trazabilidad.py`, sin guion bajo. Pareto los necesita desde fuera del motor.
2. **Pareto fuera del motor:** mover `pareto.py` a `procesamiento/analitica/`. Solo puede importar los nombres públicos del motor (`resolver`, `huella_escenario`, `INTERVENCIONES_CAPA`, `EscenarioInvalido`) y el módulo de trazabilidad.
3. **Imports:** quitar `comparar`, `costo_escenario` y `frontera_pareto` de `motor/__init__.py`, y actualizar los imports de `backend_web/simulaciones.py` y de los servicios `pareto` y `comparacion`.
4. **Verificación:** ningún import de `procesamiento/analitica/` trae un nombre con guion bajo, y `python -m pytest procesamiento/tests` pasa.

### Documentos y datos

- **Arquitectura v3:** escribir la unidad de la frontera (personas-día) y la de los costos (pesos).
- **`cost_unit`** de cada tipo de intervención: escribir la unidad en pesos. La columna existe desde la migración 014. Si los valores ya están cargados en una migración, el cambio va en una migración nueva, no editando la anterior.
- **Fuentes de precios:** revisar en `intervention_types` qué costos tienen `cost_source` y cuáles son supuesto. No se muestran en pesos sin esa marca (regla 8 de `AGENTS.md`).

### Preguntas abiertas

- ¿Cómo entra la vacunación a la frontera? La propuesta da dos opciones: como indicador aparte (dosis), o sin costo en la frontera.

## Cambios pendientes por D7

D7 quedó aceptada el 2026-11-08 con la opción C, la tercera de la propuesta (ver [`D07-politica-de-migraciones.md`](D07-politica-de-migraciones.md)). Estos cambios no están implementados.

### Reglas y herramientas

- **README de migraciones:** escribir las dos reglas. Esquema: nunca se edita un archivo aplicado; siempre un número nuevo. Datos (valores de un `INSERT`): se corrigen en el archivo de migración y en el bloque del dump, juntos, con una migración correctiva idempotente.
- **Regla 6 de `AGENTS.md`:** agregar la excepción para valores de datos. Hoy dice que nunca se edita una migración aplicada.
- **`verifica_migraciones.py`:** confirmar que sigue detectando diferencias entre el dump y las migraciones. Es lo que sostiene la regla de datos.
- **Migraciones correctivas:** cada una debe ser idempotente. Hay que probar que correrla dos veces no cambia nada.
- **Base de pruebas** (`datos/scripts/prepara_base_pruebas.py`): revisar que se arme desde las migraciones y el dump.
- **D16:** depende de D7. Revisar que su texto siga valiendo.

## Cambios pendientes por D8

D8 está como propuesta (ver [`D08-replicas-de-una-comparacion.md`](D08-replicas-de-una-comparacion.md)): el analista configura las réplicas, con piso de referencia 30 y confirmación por debajo; el resumen muestra media, mediana e intervalo entre percentiles 5 y 95. Falta que el equipo la confirme. Estos cambios no están implementados.

### Código y base de datos

- **Escritorio, réplicas:** hecho en el MVP de `frontend_desktop`, del lado del cliente. La app lanza N corridas por versión (semillas 1..N; 30 por omisión, máximo 100 por el tope de `GET /runs`) y pide confirmación con menos de 30. Los servicios no cambiaron: cada réplica queda como un lote de una corrida.
- **Escritorio, resumen:** hecho también en el cliente (`frontend_desktop/app/resumen.py`): media, mediana y percentiles 5 y 95 por escenario, sobre las semillas comunes a las versiones comparadas. La frontera se calcula sobre medianas. D8 sigue en propuesta. Si se confirma con lotes en el servidor, este cálculo pasa a `corridas`, `comparacion` y `pareto`.
- **Tope:** la base ya tiene `max_replicas_por_lote` (200) y `replicas_por_defecto` (30) en `system_settings` (migración 010). Ningún código las lee hoy; hay que usarlas.
- **Web:** no lanza corridas (D4). Solo muestra lo que se corrió.

### Preguntas abiertas

- ¿La frontera de Pareto se calcula sobre las medianas? La propuesta lo recomienda; no está confirmado.
- ¿Se muestra un aviso cuando las bandas de dos escenarios se enciman? La propuesta lo recomienda; no está confirmado.

## Cambios pendientes por D6

D6 está como propuesta: la opción D, un factor de escala que el analista ajusta en la app de escritorio (ver [`D06-poblacion-del-escenario.md`](D06-poblacion-del-escenario.md)). Falta investigar si el motor la puede usar. No hay código por cambiar todavía.

### Investigar antes de implementar

- **Dónde entra la población al motor:** hoy el SEIR (`python-ref`) recibe `population_size` como conteo por grupo de edad (migración 023). Revisar `procesamiento/motor/`.
- **Dentro o fuera del motor:** si el factor entra al motor, cambia la dinámica del contagio. Si se aplica solo a los casos y muertes que se muestran (como la opción C), solo cambia la escala de los números.
- **Validación:** decidir si el factor se valida contra el censo o se guarda como supuesto (regla 8 de `AGENTS.md`).

### Si se confirma

- **Esquema:** guardar el factor en la versión, con una migración nueva después de las que ya están pendientes (D1 y D2).
- **App de escritorio:** campo para ajustar el factor. Se construye en el tercer parcial (D10).
- **Web:** solo muestra el factor y los habitantes representados de la versión.

## Cambios pendientes por D18 y D20

D18 y D20 quedaron aceptadas el 2026-11-08 (ver [`D18-un-postgres-un-rol-por-servicio.md`](D18-un-postgres-un-rol-por-servicio.md) y [`D20-web-directa-a-postgres.md`](D20-web-directa-a-postgres.md)). D17 también quedó aceptada; no pide cambios. Estos cambios no están implementados.

### Preguntas abiertas

- **Rol del monolito (D18):** hoy la web corre como `epidemia_app`, que se crea a mano (`docs/INSTALACION.md`) y tiene SELECT, INSERT, UPDATE y DELETE sobre todas las tablas. Las migraciones 026 a 030 dicen que no lo tocan. La regla «cada servicio escribe solo en las tablas de su dominio» no lo cubre, porque la web no es un servicio. ¿La web sigue con ese rol o recibe uno propio, con permisos acotados?
- **Roles `app_*` (D18):** la migración 009 crea `app_web`, `app_surveillance`, `app_analytics` y `app_monitoring`, y ningún código los usa. ¿Se retiran? Sería con una migración nueva; no se edita la 009.
- **Reglas de negocio en dos caminos (D20):** la web y los servicios `svc_*` escriben las mismas tablas. Por ejemplo, `backend_web/queries.py` (`crear_corrida`) y `svc_corridas` (migraciones 026 a 030) crean lotes. Con la opción A, cada regla que toque esas tablas tiene que valer en ambos caminos. Revisar cuáles ya están en los dos lados y cuáles solo en uno.

## Cambios pendientes por D25

D25 quedó aceptada el 2026-11-08 con la opción A: nginx es la entrada única, con TLS, y enruta cada servicio por su prefijo (ver [`D25-nginx-como-entrada.md`](D25-nginx-como-entrada.md)). Estos cambios no están implementados.

### Código e infraestructura

- **nginx en `infra/`:** `infra/docker-compose.yml` no tiene nginx hoy. Agregarlo, con 80 y 443 como únicos puertos abiertos.
- **Prefijo por servicio:** cada servicio debe funcionar detrás de `/<servicio>`. Revisar `/docs` y `/openapi.json`, que hoy están en la raíz de cada servicio, y el CORS: `CONSOLE_ORIGIN` se lee en `microservicios/comun/epidemia_comun/ajustes.py` y `fabrica.py`.
- **Directorio `estado-servicios`:** que devuelva `https://<dominio>/<servicio>` (ajuste de D13). Hoy `URL_PUBLICA` vale `http://localhost:{puerto}` por defecto.

### Documentos

- **D26 (certificado HTTPS)** depende de D25 y ya puede avanzar. Sigue Pendiente hasta que se decida de dónde sale el certificado.

## Cambios pendientes por D26

D26 quedó aceptada el 2026-11-08 con la opción A: certificado de Let's Encrypt para un dominio que apunta a la IP fija de la máquina (ver [`D26-certificado-https.md`](D26-certificado-https.md)). Estos cambios no están implementados.

### Infraestructura

- **Dominio:** conseguir uno, propio o un subdominio gratuito, y apuntar su registro A a la IP fija. Antes de depender de un subdominio gratuito, confirmar que su proveedor permite Let's Encrypt.
- **IP fija:** reservar una IP externa estática en Compute Engine. Si la IP cambia, el dominio y el certificado dejan de servir.
- **Certificado:** certbot obtiene el certificado y nginx (D25) lo usa. La validación pasa por el puerto 80, que D25 ya deja abierto. Montar el certificado en el contenedor de nginx y dejar programada la renovación.

### Apps

- **Android:** la app trae ISRG Root X1 porque Android 7.0 (`minSdk 24`) no la incluye de fábrica (ver D26). Hecho en `frontend_movil/`; falta probarla contra el dominio real, de preferencia también en un Android 7.0.
- **Escritorio:** `requests` confía en Let's Encrypt con las raíces de `certifi`. Probar la conexión sin excepciones.

### Preguntas abiertas

- ¿Quién consigue el dominio y con qué proveedor? Sin eso no se puede obtener el certificado.
