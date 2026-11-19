> **Estado: Vigente** · 2026-11-19 · Casilla C6 del [checklist](../parciales/parcial-3/checklist.md) · Base para D36 y E9

# Inventario: qué servicio atiende cada pantalla de la web

[Retro: «Ninguna aplicación cliente deberá conectarse directamente a PostgreSQL, MongoDB o Redis»]. Cada pantalla de `frontend_web/app/routes.py`, con lo que lee o escribe de `backend_web` y la ruta del servicio que debe atenderla según el [catálogo](microservicios.md) y `docs/contratos/`. Lo que no tiene ruta va a la tabla [«Lo que falta (E9)»](#lo-que-falta-e9), con su bloque dueño.

El orden en que pasan los módulos es el de D36. Las consultas se sacaron de las llamadas de cada vista, incluidas las de sus funciones auxiliares, y cada servicio se ubicó por la función de `backend_web` que ya usa.

**Resumen:**
- La web tiene 33 rutas y usa 71 funciones de `backend_web` (más `attempt_login`, `hash_password` y `log_audit`).
- Una ruta no pasa, porque C1 la retira. De las 32 restantes, 20 ya tienen todo en un servicio y 12 tienen al menos un hueco.
- Faltan 11 rutas o cambios: 4 de D, 4 de E y 3 de F.

## Fuera de las pantallas

| Qué | Hoy | Pasa a | Estado |
|---|---|---|---|
| Iniciar sesión (`/login`) | `auth.attempt_login`, `log_audit` (`LOGIN`, `LOGIN_FAILED`) y `sesion_redis.abre_sesion` | `auth` `POST /api/v1/auth/login`, que ya audita los dos casos | Existe |
| Cerrar sesión (`/logout`) | `sesion_redis.cierra_sesion` y `log_audit` (`LOGOUT`) | `sesiones` `POST /api/v1/sessions/logout`, que ya audita | Existe |
| Revisar la sesión en cada petición (`permisos.sesion_vigente`) | Lee Redis | Cada llamada a un servicio la revisa; un 401 manda a `/login`. `sesiones` `GET /api/v1/sessions/current` para las páginas que no llaman a nada más | Existe |
| Captcha del inicio de sesión | Propio de la web | `auth` `GET /api/v1/auth/captcha` | Existe |
| `PERMISSION_DENIED` cuando la web niega una pantalla | `log_audit` en `routes.py` | El servicio que responde 403 lo audita | **Falta** (E-4) |
| Menú y botones por rol (`inject_globals`) | Roles del token | Igual: salen del token y no llaman a nada | No cambia |
| Error de base caída (`sin_base`, `psycopg2`) | Página de «base no disponible» | El aviso de servicio no disponible de D36 | Se reemplaza |

## Pantallas

| # | Pantalla (ruta de la web) | Lo que usa de `backend_web` | Servicio y ruta | Estado |
|---|---|---|---|---|
| 1 | Tablero público `GET /` | `get_resumen_indicadores`, `get_resumen_situacion` | `indicadores` `GET /dashboard/indicators`, `GET /dashboard/situation` | Existe (públicas) |
| | | `get_curva_epidemica` | `series` `GET /series/cases` pide token, y esta pantalla es sin sesión | **Falta** (F-1) |
| 2 | Tablero `GET /dashboard` | Lo mismo que la 1 | `indicadores` y `series` `GET /series/cases` (con token) | Existe |
| 3 | Mapa `GET /mapa` y `GET /api/mapa` | `get_mapa_municipios`, `get_tendencia_zona`, `get_mapa_serie_temporal` | `zonas` `GET /zones/map` | Existe |
| | | `get_enfermedades_catalogo` (solo las que tienen casos en NL) | Ninguna ruta da esa lista | **Falta** (F-2) |
| 4 | Captura `GET,POST /reportes/nuevo` | `crear_caso`, `valida_caso`, `get_caso` y catálogos | — | **No pasa:** C1 la retira (D1) |
| 5 | Enfermedades `GET /enfermedades` | `get_enfermedades` | `enfermedades` `GET /diseases` | Existe |
| | | `get_enfermedades_stats` (las 4 tarjetas) | Ninguna ruta | **Falta** (D-1) |
| 6 | Alta de enfermedad `GET,POST /enfermedades/nueva` | `valida_enfermedad`, `crear_enfermedad`, `normaliza_codigo` | `enfermedades` `POST /diseases` | Existe |
| | | `parametros_desde_form`, `estado_parametros` | `parametros` `PUT /diseases/{id}/parameters`, `GET .../parameters/status`. Leer el formulario se queda en `frontend_web` | Existe |
| 7 | Editar enfermedad `GET,POST /enfermedades/<id>/editar` | `get_enfermedad`, `actualiza_enfermedad`, `valida_enfermedad`, `parametros_desde_form`, `estado_parametros` | `enfermedades` `GET,PUT /diseases/{id}` y `parametros` `PUT /diseases/{id}/parameters` | Existe |
| 8 | Activar o desactivar `POST /enfermedades/<id>/estado` | `get_enfermedad`, `set_enfermedad_activa` | `enfermedades` `POST /diseases/{id}/activate` y `.../deactivate` | Existe |
| 9 | `GET /export/enfermedades.csv` | `get_enfermedades` | `enfermedades` `GET /diseases`; el CSV lo arma la web | Existe |
| 10 | `GET /export/resumen.csv` | `get_resumen_situacion` y `log_audit` (`EXPORT`) | `indicadores` `GET /dashboard/situation` | Datos: existe. Auditoría: **falta** (F-3) |
| 11 | Regiones `GET /regiones` | `get_regiones_catalogo` | `regiones` `GET /regions` | Existe |
| | | `get_estado_nl` (la fila del estado) | `GET /regions` solo trae municipios, y `GET /regions/{id}` solo un municipio | **Falta** (D-2) |
| 12 | Población `GET,POST /regiones/<id>/editar` | `get_region_municipio`, `valida_poblacion_municipio`, `actualiza_poblacion_municipio` | `poblacion` `GET,PUT /regions/{id}/population` | Existe |
| 13 | Grupos de edad `GET,POST /regiones/<id>/edades` | `get_grupos_edad_municipio`, `valida_grupos_edad_municipio`, `actualiza_grupos_edad_municipio` | `poblacion` `GET,PUT /regions/{id}/age-groups` | Existe |
| 14 | Escenarios `GET /escenarios` | `get_escenarios` | `escenarios` `GET /scenarios` | Existe |
| 15 | Detalle `GET /escenarios/<id>` | `get_escenario_detalle`, `get_versiones` | `escenarios` `GET /scenarios/{id}`, `GET .../versions` | Existe |
| | | `revisa_version` | `validacion` `GET /versions/{id}/validation` | Existe |
| | | `simulaciones.escala` | `resultados` `GET /runs/{id}/results` (trae la escala) | Existe |
| 16 | Aprobar o rechazar `POST /escenarios/<id>/revisar` | `resuelve_revision` | `aprobacion` `POST /scenarios/{id}/review`, que ya avisa al autor | Existe |
| 17 | Bandeja `GET /revisiones` | `get_pendientes_revision` | `aprobacion` `GET /reviews/pending` | Existe |
| 18 | Monitoreo `GET /monitoreo` | `get_monitoreo_serie`, `_edad`, `_sexo`, `_totales` | `series` `GET /series/cases`, `.../by-age`, `.../by-sex`, `.../totals` | Existe |
| | | `get_monitoreo_zonas` | `zonas` `GET /zones` | Existe |
| | | `get_municipios_catalogo` | `regiones` `GET /regions` | Existe |
| | | `get_enfermedades_catalogo` | Igual que en el mapa | **Falta** (F-2) |
| 19 | `GET /export/monitoreo.csv` | `get_monitoreo_zonas` y `log_audit` (`EXPORT`) | `zonas` `GET /zones` | Datos: existe. Auditoría: **falta** (F-3) |
| 20 | Simulaciones `GET /simulaciones` | `get_runs_recientes` | `corridas` `GET /runs` | Existe |
| | | `listar_versiones_escenario` (todas las versiones de todos los escenarios) | Solo por escenario (`GET /scenarios/{id}/versions`): una llamada por escenario | **Falta** (D-3) |
| 21 | Corrida `GET /simulaciones/corridas/<id>` | `get_run` | `corridas` `GET /runs/{id}` | Existe |
| | | `get_resultado_run`, `resultados.curvas_de_corrida`, `simulaciones.escala`, `simulaciones.motor_de_resultado` | `resultados` `GET /runs/{id}/results`, `GET .../curves` | Existe |
| | | `buscar_run_equivalente` (otra corrida con la misma versión, semilla y huella: la demostración de reproducibilidad) | Ninguna ruta | **Falta** (E-1) |
| 22 | Estado de la corrida `GET /simulaciones/corridas/<id>/estado` | `get_run`, `simulaciones.estado_visible` | `corridas` `GET /runs/{id}`. El texto visible lo arma la web | Existe |
| 23 | Usuarios `GET /usuarios` | `get_usuarios_lista` | `usuarios` `GET /users` | Existe |
| | | `get_roles_catalogo` | `roles` `GET /roles` | Existe |
| | | `get_usuarios_resumen` (total, activos, pendientes e inactivos) | Ninguna ruta | **Falta** (E-2) |
| 24 | Alta `GET,POST /usuarios/nuevo` | `valida_usuario`, `crear_usuario`, `get_usuario`, `auth.hash_password` | `usuarios` `POST /users` | Existe |
| 25 | Editar `GET,POST /usuarios/<id>/editar` | `get_usuario`, `valida_usuario`, `actualizar_usuario` | `usuarios` `GET,PUT /users/{id}`; el rol, `roles` `PUT /roles/assignments/{id}` | Existe |
| 26 | Activar o desactivar `POST /usuarios/<id>/estado` | `get_usuario`, `desactivar_usuario` | `usuarios` `POST /users/{id}/{accion}` | Existe |
| 27 | Eliminar `POST /usuarios/<id>/eliminar` | `get_usuario`, `dependencias_usuario`, `eliminar_usuario` | `usuarios` `DELETE /users/{id}` | Existe |
| 28 | Auditoría `GET /auditoria` | `get_auditoria_lista`, `get_auditoria_resumen`, `get_acciones_auditoria`, `get_modulos_auditoria`, `get_usuarios_para_filtro` | Ningún servicio lee la bitácora (E7) | **Falta** (E-3) |
| 29 | Comparación `GET /comparacion` | `get_runs_completados_para_comparar` | `corridas` `GET /runs?status=completado` | Existe |
| | | `get_corridas_para_comparar`, `resultados.curvas_de_corrida` | `comparacion` `GET /comparisons?runs=…`, que ya pide las curvas a `resultados` | Existe |
| | | `simulaciones.construir_comparacion_costo_impacto` | `pareto` `GET /pareto?runs=…` | Existe |
| 30 | Costos `GET,POST /comparacion/costos` | `get_tipos_intervencion` | `tipos-intervencion` `GET /intervention-types` | Existe |
| | | `valida_costo_intervencion`, `actualiza_costo_intervencion` (costo de un **tipo**) | `intervenciones` solo tiene `PUT /versions/{id}/interventions/{iid}/cost`, que pide una versión en borrador | **Falta** (D-4) |

## Lo que falta (E9)

Cada bloque lo agrega en sus servicios y en su rama (D, E y F). Una ruta nueva lleva candado con los roles de la pantalla, contrato (`openapi.json`, XSD y ejemplos) y pruebas.

| # | Bloque | Servicio | Qué falta | Pantalla |
|---|---|---|---|---|
| D-1 | D | `enfermedades` | `GET /api/v1/diseases/stats`: registradas, activas, inactivas, altas en 30 días y detectadas en NL en 30 días | 5 |
| D-2 | D | `regiones` | La fila del estado, con su población agregada (por ejemplo, `GET /api/v1/regions/state`) | 11 |
| D-3 | D | `escenarios` | Lista de versiones de todos los escenarios, con nombre, enfermedad, región y estado (por ejemplo, `GET /api/v1/versions?status=`) | 20 |
| D-4 | D | `intervenciones` | Fijar el costo de un tipo sin pasar por una versión (por ejemplo, `PUT /api/v1/intervention-types/{id}/cost`). Es el dueño de esas columnas según el catálogo | 30 |
| E-1 | E | `corridas` | La corrida equivalente de una corrida: otra completada con la misma versión, semilla y huella (por ejemplo, `GET /api/v1/runs/{id}/equivalent`) | 21 |
| E-2 | E | `usuarios` | Resumen de cuentas (por ejemplo, `GET /api/v1/users/summary`) | 23 |
| E-3 | E | `roles` | Consultar la bitácora: lista filtrada y paginada, resumen y catálogos de acciones, módulos y usuarios (E7). La retroalimentación le da a `roles` la «auditoría de cambios» (D37) | 28 |
| E-4 | E | `epidemia_comun` | `requiere_token` audita `PERMISSION_DENIED` cuando responde 403 (RF-A05), para que la web no tenga que escribir en la bitácora | Todas |
| F-1 | F | `indicadores` | La curva diaria del tablero público, sin token y agregada (por ejemplo, `GET /api/v1/dashboard/curve`), como las otras dos rutas públicas de `indicadores` | 1 |
| F-2 | F | `zonas` o `series` | Las enfermedades que tienen casos en NL, para los filtros (por ejemplo, dentro de `GET /zones/map` o en `GET /series/diseases`) | 3 y 18 |
| F-3 | F | `indicadores` y `zonas` | Auditar la exportación: con `?export=1`, `GET /dashboard/situation` y `GET /zones` registran `EXPORT` en la bitácora | 10 y 19 |

Los nombres de ruta de esta tabla son propuestas. Cada bloque fija la ruta en el catálogo y en su contrato antes de crearla («Agregar o cambiar un servicio», `microservicios/AGENTS.md`).

## Al pasar cada módulo (C6)

- **Roles:** antes de pasar una pantalla, comparar sus roles (`roles_required` en `routes.py`) con los de la ruta del servicio. Si el servicio es más estricto, la pantalla deja de funcionar para ese rol; se corrige en la matriz de permisos, no en la web.
- **Forma de la respuesta:** las funciones de `backend_web` conservan su nombre y lo que regresan (D36). Si el JSON del servicio trae otros nombres, la conversión va en `backend_web`, no en las plantillas.
- **Texto para personas:** los servicios regresan claves (regla 5 de `microservicios/AGENTS.md`). Lo que hoy arma `conversion.py` o `simulaciones.estado_visible` se queda en la web.
