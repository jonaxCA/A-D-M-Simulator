# D55 - Devolver una versión para cambios y firmar la versión aprobada

Fecha: 2026-11-23 · Estado: Aceptada · Atiende RF-D16 y RF-D20 · Amplía D5 · Aplica D37

## Contexto
- La retroalimentación pide para `aprobacion` un «flujo de revisión y autorización de escenarios;
  comentarios, devolución, rechazo, aprobación, responsables y firma de versiones» (checklist, D7).
- Hoy solo se aprueba o se rechaza. Una versión rechazada no se edita: hay que crear otra. No hay
  forma de pedir una corrección menor sin cerrar la versión.
- Una versión aprobada no guarda nada que pruebe qué se aprobó. Cada corrida sí guarda la huella de
  lo que simuló (`simulation_runs.scenario_checksum`, la SHA-256 de la entrada canónica del motor,
  038 y `procesamiento/contrato.py`).
- Las reglas de revisión vivían en `backend_web.queries` (E8).

## Opciones consideradas
- **Devolver:** A) la misma versión vuelve a `borrador` con el comentario; B) un quinto estado,
  `devuelto`, que cambia `escenario.xsd` y `aprobacion.xsd`, que el escritorio valida.
- **Firma:** A) la huella SHA-256 de la entrada del motor, con quién aprobó y cuándo; B) una firma
  criptográfica (Ed25519) con una llave del servicio.

## Decisión
Devolver A y firma A, decididas con el líder el 2026-11-23. Van en la migración 064.

**Devolver** (`POST /scenarios/{id}/review` con `decision: devolver`):
- Lo hacen EPIDEMIOLOGO y ADMINISTRADOR, con comentario obligatorio. Nadie devuelve su propia
  versión.
- La misma versión vuelve a `borrador`:
  - `submitted_at`, `reviewed_by`, `reviewed_at` y `disease_params` quedan en NULL;
  - `review_comment` guarda el motivo.

  `ck_scenario_versions_revision` (013) ya lo permite. Como borrador, su autor la edita y la reenvía,
  y los parámetros se vuelven a congelar al reenviarla.
- **Rechazar** sigue cerrando la versión: para corregir hay que crear otra.
- Se avisa al autor con el tipo nuevo `SCENARIO_RETURNED`.
- Queda `UPDATE` de `scenario_versions` con `decision: devolver`.
- No hay estado nuevo, así que los XSD del escritorio no cambian.
- Un borrador con comentario es una versión devuelta (`devuelta` en el historial de `escenarios`).

**Firmar** al aprobar:
- `aprobacion` pide a `validacion` la huella de la versión.
- `validacion` la calcula con `procesamiento.entrada_motor.escenario_de_version` y
  `procesamiento.contrato.huella`, desde las mismas filas que lee `simulador`. Una prueba exige que
  las consultas sigan iguales y que la huella coincida con la del simulador.
- La huella se guarda en `scenario_versions.approval_sha256`, con `reviewed_by` y `reviewed_at`.
  Sin ella no se aprueba (503).
- Es la misma huella que guardará cada corrida de esa versión.
- `GET /api/v1/versions/{id}/signature` (ANALISTA, EPIDEMIOLOGO y ADMINISTRADOR) da:
  - la firma, quién la aprobó y cuándo;
  - la huella actual: `integra` si coinciden;
  - cuántas corridas simularon exactamente lo firmado.
- La base solo admite la firma en una versión aprobada (`ck_scenario_versions_firma`). Las
  aprobadas antes de la 064 quedan sin firma: no se inventa una.
- No hay llaves que administrar. La huella prueba **qué** se aprobó. **Quién** lo aprobó lo prueban
  el JWT de esa persona y la bitácora de solo inserción.

**E8:** el flujo de revisión pasa de `backend_web.queries` a `microservicios/aprobacion/datos.py`.
`aprobacion` deja de importar `backend_web` y su imagen parte de `epidemia/base-vigilancia`. La
bandeja ya solo trae versiones vigentes.

## Consecuencias
- RF-D16 incluye devolver y RF-D20 queda hecho. La web (C) puede ofrecer «Devolver» con el mismo
  `POST /review`.
- **Para C:** la web tiene su propia tabla de nombres de avisos (`frontend_web/app/routes.py`); le
  falta `SCENARIO_RETURNED`.
- **Para quien rehaga `ck_notifications_type`:** tiene que conservar `SCENARIO_RETURNED`. Por eso
  esto va en la 064 y no en la 042, de D: en una instalación limpia, la 057 y la 060 lo quitarían.
- **Para E (reproducibilidad, A4):** con la firma, cada corrida se puede cotejar con lo aprobado
  (`corridas.coinciden` y `corridas.distintas`).
- `escenarios` ya no deja crear una versión mientras la vigente está en revisión. Antes la anterior
  se quedaba en la bandeja y nadie la podía resolver.

Depende de: D5, D37, D54

## Fuentes
- `docs/parciales/parcial-3/RETROALIMENTACION_SEGUNDO_PARCIAL.txt` (l. 87) y el checklist (D7).
- Migraciones 013 (`ck_scenario_versions_revision` y la no autoaprobación), 024 (`disease_params`)
  y 038 (`scenario_checksum`).
- `procesamiento/contrato.py` (`huella`) y `procesamiento/entrada_motor.py`.
