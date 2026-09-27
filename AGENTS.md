# AGENTS.md

> **Estado: Vigente** · 2026-09-25
> Si algo aquí choca con lo que pide la persona en la sesión, pregunta antes de actuar.

## Contexto

Simulador de respuesta a epidemias (ver `README.md`). Proyecto universitario de ocho personas;
buena parte del código se generó con IA y el equipo no lo conoce a fondo. Prefiere cambios
pequeños, legibles y fáciles de revisar.

## Etapa actual

- Monolito: una sola app Flask conectada directo a PostgreSQL.
- Qué construir: `docs/CHECKLIST_SEGUNDO_AVANCE.md`. Su "Prueba de aceptación" define cuándo
  algo está terminado.
- El motor es un SEIR de prueba, sin agentes. Los documentos de arquitectura y de contexto
  describen el sistema final (ABM, microservicios); no es lo que se construye ahora.

## Fuera de alcance

MongoDB, Redis, colas externas, microservicios, CUDA/Numba/FLAME GPU, ABM, app móvil,
app de escritorio, contratos OpenAPI/XSD, calibración, IA predictiva, visualización 3D y
un modelo económico sofisticado. No crees código en `microservicios/`, `infra/`,
`frontend_movil/`, `frontend_desktop/` ni `docs/contratos/`.

## Reglas

1. Nada de SQL en `frontend_web`: los datos se piden a `backend_web`.
2. `procesamiento/motor` no importa Flask ni toca la base: recibe y regresa diccionarios.
3. Cada ruta nueva lleva candado; ocultar un botón no es control de acceso. Los permisos por
   rol viven en `role_permissions` (migración 010); si la ruta no encaja, pregunta.
4. Todo cambio de datos se registra con `log_audit()`.
5. Gráficas con Highcharts (requisito de la materia); interfaz responsive y en español.
6. El esquema son las migraciones de `datos/postgres/migraciones/`, no los documentos.
   Nunca edites una migración aplicada, y confirma el número antes de crear una.
7. Usa los estados de la base. Versiones: `borrador`, `en_revision`, `aprobado`, `rechazado`.
   Corridas: `encolado`, `ejecutando`, `completado`, `fallido`, `cancelado`.
8. No inventes cifras: todo parámetro de enfermedad o costo lleva su fuente o la marca de
   supuesto. Si falta un dato, el sistema se niega a simular.
9. Las pantallas de resultados muestran el aviso de que no es una predicción (`AVISO_SIMULACION`).
10. La comparación muestra opciones y costos; no recomienda un escenario.
11. El código debe correr en Python 3.9: sin `match` ni `X | Y` en anotaciones.

## Comandos

- Sitio: `python -m frontend_web.run`. El paso 5 de `docs/INSTALACION.md` dice `python app.py`: está mal.
- `docker compose up`, que menciona `CONTRIBUTING.md`, todavía no existe.
- Verificar que el dump coincide con las migraciones: `python datos/scripts/verifica_migraciones.py`.

## Decisiones abiertas: pregunta antes de implementar

- Quién captura casos, quién aprueba versiones y quién consulta la auditoría.
- Cuántas réplicas usa una comparación y cómo se resumen.
- Si la población de un escenario son habitantes o agentes simulados.
- Unidad de costo: personas-día, pesos o ambos por separado.
- Si una versión guarda una copia de los parámetros de la enfermedad al enviarse a revisión.
- Qué parte del trabajo con escenarios queda en la web y qué en la app de escritorio.
- Política para corregir datos en migraciones aplicadas. Por eso `verifica_migraciones.py`
  hoy falla en `010`: es una diferencia conocida, no la corrijas.

Cuando se decidan, quedarán en `docs/decisiones.md`.

## Qué manda cuando dos fuentes se contradicen

1. Lo que pida la persona en la sesión.
2. `docs/decisiones.md`.
3. Este archivo.
4. `docs/CHECKLIST_SEGUNDO_AVANCE.md`.
5. `docs/arquitectura/arquitectura_v1.md`.
6. `docs/contexto/simulador.md`.

Para el esquema de la base, las migraciones ganan sobre cualquier documento.

## Temporal: partes viejas del checklist (borrar cuando se corrijan)

- Rutas: `db/` es ahora `datos/postgres/`, `data/censo/` es `datos/censo/` y `motor/` es
  `procesamiento/motor/`.
- Estados PENDIENTE, COMPLETADA y ERROR: usa los de la regla 7.
- La última casilla del bloque E dice que ninguna enfermedad se puede simular; desde la 017,
  COVID-19 e influenza sí se pueden.

## Git y cierre

- Sigue `CONTRIBUTING.md`. Si la tarea corresponde a una casilla del checklist, márcala en el mismo PR.
- Antes de dar una tarea por terminada:
  - Las pruebas del motor pasan.
  - Si tocaste `datos/`, `verifica_migraciones.py` no muestra diferencias nuevas.
  - Probaste con un rol que debe poder entrar y con uno que no.
