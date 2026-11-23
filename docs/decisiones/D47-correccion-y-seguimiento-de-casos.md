# D47 - Corrección y seguimiento de casos con control de versión

Fecha: 2026-11-22 · Estado: Aceptada · Reabre RF-C11 y RF-C15 · Cambia D32 (los casos ya se corrigen) · Amplía D1

## Contexto
La retroalimentación pide actualizar los casos y darles seguimiento, sin sobrescribir en silencio
lo que cambió otro profesional, y avisar de los registros rechazados. Hoy `casos` solo registra y
consulta (D32): `status` existe (`pendiente`, `validado`, `duplicado`, `descartado`), pero nadie lo
cambia, y la sincronización no puede tener conflictos porque nada se edita. Los permisos ya
existían en la migración 010: `cases.update` (CAPTURISTA y EPIDEMIOLOGO) y `cases.approve`
(EPIDEMIOLOGO).

## Opciones consideradas
- Concurrencia: A) el último gana; B) versión del caso y If-Match (control optimista); C) bloquear
  el caso mientras alguien lo edita.
- Historial: A) la bitácora (`audit_log`); B) una tabla propia del caso.
- Quién corrige: A) solo el EPIDEMIOLOGO; B) también el CAPTURISTA, solo sus casos pendientes.

## Decisión
- **Concurrencia: B.** `cases.version` empieza en 1 y cada corrección o cambio de estado la sube en
  1; el `ETag` de `GET /cases/{id}` es esa versión. Quien cambia el caso la manda en `If-Match`: si
  el caso cambió desde entonces, **412** con el `ETag` actual y nada se toca; sin `If-Match`,
  **428**. El caso se bloquea (`FOR UPDATE`) dentro de la transacción, así que dos cambios a la
  vez se forman en fila. Sin bloqueos largos (C), que se quedarían colgados con un teléfono sin red.
- **Corregir (`PATCH /cases/{id}`):** el EPIDEMIOLOGO, cualquier caso `pendiente` o `validado`; el
  CAPTURISTA, solo los que capturó y mientras estén `pendiente` (opción B, con `cases.update` de la
  010). Solo los campos del caso (`disease_id`, `region_id`, fechas, edad, sexo, coordenadas,
  resultado y gravedad), validados junto con el resto, igual que al capturarlo; nunca
  `local_uuid`, `reported_by` ni `device_id`. Uno `descartado` o `duplicado` se reabre antes. Si
  nada cambia, no sube la versión.
- **Estado (`POST /cases/{id}/status`):** solo el EPIDEMIOLOGO (`cases.approve`). Transiciones:
  `pendiente` → `validado`, `descartado` o `duplicado`; `validado` → `descartado`, `duplicado` o
  `pendiente`; `descartado` y `duplicado` → `pendiente` (reabrir). Descartar, marcar duplicado y
  reabrir piden motivo (`status_reason`); duplicado, además, el caso original (`duplicate_of`: existe,
  es de la misma enfermedad y no es otro duplicado). El ADMINISTRADOR no valida: es una decisión
  clínica, y D1 ya le quitó la captura.
- **Historial: B.** `case_history`, una fila por cambio: la versión que dejó, quién y cuándo, el
  estado antes y después, `changes` (`{campo: {antes, despues}}`), el motivo y el dispositivo si vino
  de la móvil. `GET /cases/{id}/history` lo da a los cuatro roles que leen casos. Además se audita
  `UPDATE` (la bitácora sigue siendo del ADMINISTRADOR, D1).
- **Avisos:** al descartar o marcar duplicado, quien capturó el caso recibe `CASE_REJECTED` de
  `notificaciones` (best-effort: si no responde, el cambio ya quedó).
- **Sincronización:** el lote acepta `updates`, las correcciones hechas sin conexión con la versión
  que tenía el teléfono. Cada una va a `PATCH /cases/{id}` con `If-Match` y su resultado es
  `actualizado`, `conflicto` (con el caso como está en el servidor, para que la app lo muestre y
  la persona decida) o `rechazado`. Un lote que falló a medias y se reenvía no marca como conflicto
  una corrección que ya había entrado (el caso ya tiene lo pedido).
- Migración 057: las columnas `version`, `updated_at`, `updated_by`, `status_reason` y
  `duplicate_of`, la tabla `case_history`, el tipo `CASE_REJECTED` y los `GRANT` de `svc_casos`
  (actualiza solo esas columnas).

## Consecuencias
- RF-C11 (corregir un caso) y RF-C15 (marcarlo como erróneo con motivo) vuelven al alcance.
- Los casos que ya existían quedan en la versión 1, sin historial; uno que ya estaba `duplicado`
  se queda sin `duplicate_of`.
- La app móvil (B4) puede corregir sin conexión y mostrar los conflictos; la web y el escritorio
  pueden validar y descartar. Ninguno lo hace todavía: este cambio es del servidor.
- La consola de pruebas puede mandar `If-Match` y leer el `ETag` (CORS).
- Pendiente: el alcance por región (D43) no se aplica todavía a los casos.
