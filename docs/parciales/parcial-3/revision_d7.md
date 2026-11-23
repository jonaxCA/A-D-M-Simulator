# Revisión de los servicios del bloque D contra la retroalimentación (D7)

Revisado el 2026-11-23 contra [`RETROALIMENTACION_SEGUNDO_PARCIAL.txt`](RETROALIMENTACION_SEGUNDO_PARCIAL.txt)
(servicios 5 a 9 y 12 a 16, y lo del escritorio sobre proyectos), con el código de
`feat/tercer-parcial` (`6f70777`). Los servicios del bloque D son `enfermedades`, `parametros`,
`regiones`, `poblacion`, `tipos-intervencion`, `escenarios`, `intervenciones`, `aprobacion`,
`validacion` y `escenarios-xml` («Dueños de los servicios» del [checklist](checklist.md));
`evidencias` (D2) e `importacion` (D6) ya se cerraron aparte.

**Cumple** = hay ruta y prueba. **Parcial** = una parte, o solo de lectura. **Falta** = no existe.
Lo que se cerró después de la revisión dice **Hecho**, con su fecha. Catálogos se cerró el mismo día con [D58](../../decisiones/D58-catalogos-con-fuente-y-versiones.md).

El trabajo va en dos partes, decididas con el líder el 2026-11-23: primero **Escenarios** (lo que
espera el escritorio, A4), con D54 y D55; después **Catálogos**, que necesita investigar fuentes
(definiciones de caso oficiales y efectividad de cada intervención).

## Escenarios

### `escenarios` (5231)

> Creación, duplicación, consulta, edición versionada y archivado; asociación de enfermedad,
> población, condiciones iniciales y horizonte temporal.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Creación | **Cumple** | `POST /scenarios`: escenario y versión 1 en una transacción, validada por `validacion` |
| Duplicación | **Cumple** | `POST /scenarios/{id}/duplicate`, con las intervenciones; desde el 2026-11-23 se queda en el proyecto del original |
| Consulta | **Cumple** | Lista con búsqueda, detalle de cualquier versión e historial |
| Edición versionada | **Cumple** | Cambiar es crear la versión siguiente (D5); las anteriores no se tocan. **Hecho** (2026-11-23): ya no se crea una versión mientras la vigente está en revisión (antes la anterior quedaba en la bandeja sin poder resolverse) |
| Archivado | **Hecho** (2026-11-23, D54) | `POST /scenarios/{id}/archive` y `/restore`: solo lectura, sin versiones, intervenciones, envíos ni corridas (la base las rechaza), fuera de la lista salvo `?archived=true` |
| Enfermedad, población, condiciones iniciales, horizonte | **Cumple** | `disease_id` y `region_id` en el escenario; población (o censo por edad), infectados iniciales y horizonte por versión |
| Proyectos de investigación (escritorio) | **Hecho** (2026-11-23, D54) | `/projects`: agrupan escenarios de una enfermedad y una región, con objetivo, periodo y motores; `PUT /scenarios/{id}/project`. Falta la pantalla (A4) |
| Historial: quién creó, modificó, revisó o aprobó | **Hecho** (2026-11-23) | `roles` ya lo tenía por entidad (`/audit/history`, D43, RF-L13); `GET /scenarios/{id}/versions` agrega los responsables de cada versión (autor, envío, revisor, devolución y firma) |
| Perfiles de solo lectura (D42) y alcance (D43) | **Hecho** (2026-11-23) | Leen también INVESTIGADOR y AUTORIDAD_SANITARIA; las listas filtran por región y lo de fuera es 403 |

### `intervenciones` (5232)

> Programación temporal de intervenciones, intensidad, cobertura, duración, población objetivo,
> costos y relaciones con escenarios.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Programación temporal y duración | **Cumple** | `start_day` y `end_day` dentro del horizonte; no se enciman dos del mismo tipo |
| Intensidad y cobertura | **Cumple** | `coverage` y `compliance` de 0 a 1, y los parámetros de cada tipo (`reduccion`, `eficacia`, `dosis_diarias`) |
| Población objetivo | Parcial | La capa sale del tipo (`target_layer`), más `prioridad` y `edad_minima` en la vacunación; `target_region_id` existe en la tabla pero no se escribe |
| Costos | Parcial | Por tipo de intervención (`unit_cost`, personas-día): cambiarlo desde una intervención cambia el de todas las de su tipo; no hay costo por intervención |
| Relaciones con escenarios | Parcial | Cada intervención es de una versión; no hay consulta de qué escenarios usan un tipo |
| Escenario archivado | **Hecho** (2026-11-23) | 409 al agregar, quitar o mover, y `editable` falso |

### `aprobacion` (5233)

> Flujo de revisión y autorización de escenarios; comentarios, devolución, rechazo, aprobación,
> responsables y firma de versiones.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Flujo de revisión y autorización | **Cumple** | `borrador` → `en_revision` → `aprobado` o `rechazado`, con el motor revisado por `validacion` y los parámetros congelados al enviar |
| Comentarios | Parcial | Uno por dictamen (`review_comment`, hasta 1,000 caracteres); no hay hilo de comentarios |
| Devolución | **Hecho** (2026-11-23, D55) | `decision: devolver` regresa la misma versión a borrador con el motivo, y se avisa `SCENARIO_RETURNED` |
| Rechazo | **Cumple** | Con motivo obligatorio (también en la base) y aviso al autor |
| Aprobación | **Cumple** | Nadie aprueba lo que creó (en la ruta, en `datos.py` y en la base) |
| Responsables | **Cumple** | Autor, revisor y fechas por versión; quién envió está en la bitácora. Desde el 2026-11-23 también en el historial de `escenarios` |
| Firma de versiones | **Hecho** (2026-11-23, D55) | `approval_sha256`, la huella de la entrada del motor al aprobar, y `GET /versions/{id}/signature`, que la verifica y la coteja con las corridas |
| Sin `backend_web` (E8) | **Hecho** (2026-11-23) | Sus reglas pasaron a `aprobacion/datos.py` y su imagen parte de `epidemia/base-vigilancia` |

### `validacion` (5234)

> Comprobación de parámetros y coherencia matemática, unidades, valores extremos, datos faltantes y
> compatibilidad de los escenarios con el motor seleccionado.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Parámetros y coherencia matemática | Parcial | El motor exige parámetros positivos, tasas de 0 a 1, grupos de edad completos, infectados ≤ población y el reparto del censo; no hay reglas de plausibilidad entre parámetros (por ejemplo, un R0 máximo por enfermedad) |
| Unidades | Falta | Las unidades están en la especificación de `parametros` (`/status`), pero `validacion` no las revisa |
| Valores extremos | Parcial | Solo los límites duros (población, días y el `param_schema` de cada intervención) |
| Datos faltantes | **Cumple** | «Falta el parámetro…», y un aviso por parámetro sin fuente ni marca de supuesto |
| Compatibilidad con el motor seleccionado | Parcial | Un solo `resolver` para los tres motores; ninguna ruta recibe el motor |
| Huella de una versión | **Hecho** (2026-11-23, D55) | `GET /versions/{id}/validation` da `huella`, con la que `aprobacion` firma |

### `escenarios-xml` (5235)

> Importación y exportación de escenarios mediante XML, validación XSD, reportes de errores y
> compatibilidad entre versiones de contratos.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Importación y exportación | **Cumple** | `POST /scenarios/import` y `GET /scenarios/{id}/export` |
| Validación XSD | **Cumple** | `xmlschema` y `defusedxml`; el export valida su propia salida |
| Reportes de errores | **Cumple** | 422 con `errores: [{ruta, mensaje}]`, hasta 50. Si la importación falla a la mitad no deshace lo creado; lo explica en el mensaje |
| Compatibilidad entre versiones de contratos | Falta | `esquema` es fijo (`1.0`); no hay conversión de versiones anteriores |

## Catálogos

### `enfermedades` (5211)

> Catálogo de enfermedades, definiciones de caso versionadas, características epidemiológicas,
> clasificación, estado y fuentes de referencia.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Catálogo y estado | **Cumple** | Alta, edición, activar y desactivar (baja lógica), exportación auditada y estadísticas |
| Características epidemiológicas | Parcial | Solo los parámetros (son de `parametros`) |
| Clasificación | **Hecho** (2026-11-23, D58) | `transmission` (respiratoria o vectorial) e `icd10` en la ficha, con su fuente (DGE y, para COVID-19, la OMS); se cambian con `PUT /diseases/{id}` y su fuente |
| Fuentes de referencia | **Hecho** (2026-11-23, D58) | La clasificación y cada definición de caso llevan su fuente (documento, fecha y páginas), además de la de cada parámetro |
| Definiciones de caso versionadas | **Hecho** (2026-11-23, D58) | `/diseases/{id}/case-definitions`: borrador, vigente (una por enfermedad) y retirada; lo publicado no cambia. La 042 trae las de la DGE: enfermedad respiratoria viral de 2023 (COVID-19 e influenza), influenza de 2021 retirada, y dengue, paludismo y zika de 2021 |

### `parametros` (5212)

> Parámetros de transmisión, incubación, recuperación, mortalidad y hospitalización; unidades,
> límites, fuentes, incertidumbre, versionamiento y validaciones epidemiológicas.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Transmisión, incubación, recuperación, mortalidad y hospitalización | **Cumple** | `r0`, `incubacion_dias`, `infeccioso_dias`, `letalidad`, `tasa_hospitalizacion` y `dias_hospitalizacion` |
| Unidades y límites | **Cumple** | `unidad`, `min` y `max` de cada parámetro; `/status` los da |
| Fuentes | **Cumple** | Fuente o marca de supuesto obligatoria (RF-B09) |
| Validaciones epidemiológicas | Parcial | Rango por parámetro; nada entre parámetros |
| Incertidumbre | **Hecho** (2026-11-23, D58) | Cada parámetro puede llevar `intervalo` (min, max y tipo IC95, RIC o rango) que contiene el valor; `/parameters/status` lo muestra. La 042 trae los que ya daban las fuentes citadas (6 parámetros de COVID-19 e influenza) |
| Versionamiento | **Hecho** (2026-11-23, D58) | Cada cambio guarda la versión completa con su motivo (`/parameters/versions`); la 1 son los parámetros de antes del historial. Cada versión de escenario sigue congelando su copia (D5) |

### `regiones` (5213)

> Países, estados, municipios, áreas sanitarias, geometrías, jerarquías geográficas, búsqueda
> territorial y datos para mapas.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Estados y municipios | **Cumple** | Nuevo León y sus 51 municipios, con población y 60 y más |
| Países | Fuera (D58) | El sistema es de Nuevo León; una fila de México cambiaría dos CHECK de `regions` y el código que supone que el estado no tiene padre |
| Áreas sanitarias | **Hecho** (2026-11-23, D58) | Las 8 jurisdicciones de NL en la base (043, del mismo archivo que usa `zonas`): `/health-areas`, `/health-areas/{numero}` y `/regions/{id}/health-areas`; Monterrey está en tres, en parte |
| Geometrías y datos para mapas | Parcial | Las sirve `zonas` (`/zones/geometry` y `/zones/map`); `regiones` solo tiene centroides y no los publica |
| Jerarquías geográficas | **Hecho** (2026-11-23, D58) | `/regions/{id}/children`: los municipios del estado; con las jurisdicciones como agrupación sanitaria |
| Búsqueda territorial | **Hecho** (2026-11-23, D58) | `/regions/search?q=`: estado, municipios (nombre o clave) y jurisdicciones, sin importar acentos; ubicar un punto sigue en `zonas` (`/zones/locate`) |

### `poblacion` (5214)

> Poblaciones por región, edad y otros grupos pertinentes; versiones, periodos de referencia,
> distribución demográfica, validación y consistencia poblacional.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Por región y edad; distribución | **Cumple** | Cinco grupos de edad más edad no especificada |
| Otros grupos | Falta | El censo trae hombres y mujeres de 60 y más, pero no se cargan |
| Validación y consistencia | **Cumple** | La suma de los grupos se conserva, total ≥ 60 y más, motivo obligatorio, 409 si otro cambió antes, y el estado es la suma de sus municipios |
| Versiones | **Hecho** (2026-11-23, D58) | Cada ajuste guarda la versión siguiente de la región y, si cambió, la del estado (`/regions/{id}/population/versions`), en la misma transacción: la corrección pasó de `backend_web` a `poblacion` (E8) |
| Periodos de referencia | **Hecho** (2026-11-23, D58) | La serie de censos y conteos de INEGI 1990-2020 por región (043, `/regions/{id}/population/periods`), y cada versión dice su año de referencia |

### `tipos-intervencion` (5215)

> Catálogo de intervenciones como vacunación, aislamiento, pruebas y medidas de reducción de
> contactos; parámetros permitidos, costos y supuestos de efectividad.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Catálogo | **Cumple** | Seis tipos: vacunación, prueba y aislamiento, reducción de aforo, cierre de escuelas, cierre de trabajo y cubrebocas |
| Parámetros permitidos | **Cumple** | `param_schema` (JSON Schema con mínimo, máximo, opciones y obligatorios) |
| Costos | **Cumple** | Costo unitario y personas-día, con fuente o supuesto (los escribe `intervenciones`) |
| Supuestos de efectividad | **Hecho** (2026-11-23, D58) | `/intervention-types/{code}/effectiveness`: valor de referencia, rango, fuente y marca de supuesto, general o por enfermedad; la 042 trae siete con fuente (Chu, Polack, Osterholm, Li y la movilidad de Google en NL). No cambian lo que se simula |

## Lo que cruza a todos

- **E8:** `aprobacion`, `poblacion` y `tipos-intervencion` ya no importan `backend_web`, y
  `parametros` tampoco (usa los límites del motor y sigue en `epidemia/base`). La regla de los
  rangos de los parámetros dejó `epidemia_comun/validaciones.py` (2026-11-23). Siguen
  `enfermedades`, `regiones`, `escenarios`, `intervenciones`, `validacion` y `escenarios-xml`.
- **D43:** `escenarios` aplica el alcance por región desde el 2026-11-23. `intervenciones`,
  `aprobacion` (envío, dictamen y bandeja) y `escenarios-xml` (exportar) todavía no.
- **D42:** en los catálogos, las lecturas son públicas, así que INVESTIGADOR y AUTORIDAD_SANITARIA ya
  las ven.

## Qué sigue, por tamaño

| Tamaño | Qué | Servicio |
|---|---|---|
| ~~Mediano~~ | **Hecho** el 2026-11-23 (D54): proyectos de investigación y archivado | `escenarios` |
| ~~Mediano~~ | **Hecho** el 2026-11-23 (D55): devolver y firmar; sin `backend_web` | `aprobacion` y `validacion` |
| Chico | Alcance de D43 en `intervenciones`, `aprobacion` y `escenarios-xml` | los tres |
| ~~Mediano~~ | **Hecho** el 2026-11-23 (D58): supuestos de efectividad por tipo, con fuente o marca de supuesto | `tipos-intervencion` |
| ~~Mediano~~ | **Hecho** el 2026-11-23 (D58): intervalo de incertidumbre y versiones de los parámetros | `parametros` |
| ~~Mediano~~ | **Hecho** el 2026-11-23 (D58): versiones y periodos de referencia de la población | `poblacion` |
| ~~Mediano~~ | **Hecho** el 2026-11-23 (D58): jerarquía, jurisdicciones sanitarias y búsqueda territorial (sin país) | `regiones` |
| ~~Grande~~ | **Hecho** el 2026-11-23 (D58): definiciones de caso versionadas con su fuente oficial, y clasificación | `enfermedades` |
| Chico | Los sexos de la población (el censo cargado solo los trae para 60 y más) | `poblacion` |
| Grande | Unidades, plausibilidad entre parámetros y compatibilidad por motor | `validacion` |
| Grande | Compatibilidad entre versiones del contrato XML | `escenarios-xml` |
| Transversal | Dejar de importar `backend_web` (E8) | los nueve restantes |
