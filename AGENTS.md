# AGENTS.md

> **Estado: Vigente** · 2026-10-28
> Si algo aquí choca con lo que pide la persona en la sesión, pregunta antes de actuar.

## Contexto

Simulador de respuesta a epidemias (ver `README.md`). Proyecto universitario: seis personas
programan. Buena parte del código se generó con IA y el equipo no lo conoce a fondo. Prefiere
cambios pequeños, legibles y fáciles de revisar.

## Etapa actual: segundo parcial

- **Sistema web:** el monolito Flask sigue conectado directo a PostgreSQL y **no llama a los
  microservicios**.
- **Microservicios:** 26 servicios Flask pequeños en `microservicios/`, cada uno en su
  contenedor de Docker, con Redis y JWT. Son para las apps de escritorio (XML) y móvil
  (JSON), que se entregan en el tercer parcial; mientras tanto, la consola de pruebas hace
  sus veces.
  - Antes de tocar esa carpeta, lee `microservicios/AGENTS.md`.
  - El catálogo de servicios está en `docs/arquitectura/microservicios.md` y las tareas en
    `docs/CHECKLIST_SEGUNDO_PARCIAL.md`.
- **Motor:** un SEIR de prueba, sin agentes. Los documentos de arquitectura y de contexto
  describen el sistema final (ABM, MongoDB, Cloud Storage, nginx); no es lo que se construye
  ahora.

## Fuera de alcance

MongoDB, Google Cloud Storage, nginx, CUDA/Numba/FLAME GPU, ABM, calibración, IA predictiva,
visualización 3D, límites de consumo y un modelo económico sofisticado.

Las apps de escritorio y móvil se entregan en el tercer parcial (D10 de `docs/decisiones.md`).
La móvil ya se empezó: su código va en `frontend_movil/`; lee antes su `README.md`. En
`frontend_desktop/` todavía no crees código.

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

- Sitio: `python -m frontend_web.run`.
- Microservicios: `python infra/genera_env.py` (crea `infra/.env` con las contraseñas) y
  `docker compose -f infra/docker-compose.yml --profile '*' up -d --build --wait`. Levanta
  PostgreSQL con la base de la demostración, Redis y los servicios.
- Pruebas de los microservicios y de la biblioteca común:
  `python -m pytest microservicios`.
- Pruebas del motor: `python -m pytest procesamiento/tests`. Se corren desde la raíz, igual
  que todo lo demás.
- Verificar que el dump coincide con las migraciones: `python datos/scripts/verifica_migraciones.py`.
- Las pruebas corren contra `<base>_pruebas`, nunca contra la de la demostración. Se crea con
  `python datos/scripts/prepara_base_pruebas.py` (ver `docs/INSTALACION.md`).

## Decisiones abiertas: pregunta antes de implementar

Cada una tiene su número en `docs/decisiones.md`:

- Quién captura casos, quién aprueba versiones y quién consulta la auditoría (D1).
- El papel del SEIR (D2).
- Unidad de costo: personas-día, pesos o ambos por separado (D3).
- Qué parte del trabajo con escenarios queda en la web y qué en la app de escritorio (D4).
- Si la población de un escenario son habitantes o agentes simulados (D6).
- Política para corregir datos en migraciones aplicadas (D7).
- Cuántas réplicas usa una comparación y cómo se resumen (D8; se revisa en el tercer
  parcial).

D5 ya se tomó: una versión es una fotografía. Guarda su población por grupo de edad y congela
los parámetros de la enfermedad al enviarse a revisión (migraciones 023 y 024). Para una
versión que ya salió de borrador, usa sus parámetros congelados, no los del catálogo.

Las de los microservicios (formato, entregas, rutas, pasarela, pruebas, XSD y migraciones)
ya están tomadas: son D9 a D16, resumidas en `microservicios/AGENTS.md`. Cuando se tome una
de esta lista, se marca en `docs/decisiones.md` y se quita de aquí.

## Qué manda cuando dos fuentes se contradicen

1. Lo que pida la persona en la sesión.
2. `docs/decisiones.md`.
3. Este archivo.
4. `docs/arquitectura/arquitectura_v1.md`.
5. `docs/contexto/simulador.md`.

Para el esquema de la base, las migraciones ganan sobre cualquier documento. Dentro de
`microservicios/`, `infra/` y `docs/contratos/`, el catálogo
(`docs/arquitectura/microservicios.md`) y el `AGENTS.md` de cada carpeta ganan sobre este
archivo.

## Git y cierre

- Sigue `CONTRIBUTING.md`.
- Antes de dar una tarea por terminada:
  - Las pruebas del motor pasan.
  - Si tocaste `datos/`, `verifica_migraciones.py` no muestra diferencias nuevas.
  - Probaste con un rol que debe poder entrar y con uno que no.

## Estilo de programación

Escribe código en Python minimalista e idiomático. Sin cadenas de documentación, sin comentarios a menos que algo no resulte obvio, sin validación de entradas más allá de lo necesario, sin clases a menos que se requiera estado, y da preferencia a la biblioteca estándar.
