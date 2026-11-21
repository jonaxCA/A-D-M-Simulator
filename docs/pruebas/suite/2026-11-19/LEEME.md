# Suite consolidada · 2026-11-19

[Retro: «ejecutar todas las pruebas sobre una base inicializada desde cero, consolidar el resultado final… No deben presentar pruebas de distintas versiones como si correspondieran a una sola ejecución»].

Una sola ejecución de `pytest` sobre una sola versión del código, con una base creada desde cero para esta corrida.

| Qué | Valor |
|---|---|
| Rama y commit | `segundo-parcial-correccion`, `075712f` (árbol sin cambios pendientes) |
| Base | PostgreSQL 16.15 en un contenedor nuevo; base de pruebas creada con `datos/scripts/prepara_base_pruebas.py` (dump, semillas y permisos); `verifica_migraciones.py` sin diferencias |
| Carpetas | `backend_web`, `frontend_web`, `microservicios`, `procesamiento` y `frontend_desktop`, en una sola invocación |
| Resultado | **2281 pasan, 2 fallan, 182 se saltan** (5 min 36 s) |

## Archivos

- [`encabezado.txt`](encabezado.txt): versión, base y resultado de cada paso.
- [`pytest.txt`](pytest.txt): la salida completa, con el detalle de cada falla y de cada prueba saltada.
- [`junit.xml`](junit.xml): el mismo resultado en formato JUnit.
- [`prepara_base.txt`](prepara_base.txt) y [`verifica_migraciones.txt`](verifica_migraciones.txt).

## Las 2 fallas: ya existían antes de estas correcciones

| Prueba | Por qué falla | Dónde se corrige |
|---|---|---|
| `backend_web/tests/test_notificaciones.py::…test_aviso_a_un_rol_salta_a_los_inactivos_y_audita_cada_uno` | La semilla de pruebas no trae un EPIDEMIÓLOGO inactivo, que la prueba exige | Semilla de pruebas (`datos/postgres/semillas/`, por su generador) |
| `frontend_desktop/tests/test_xmlio.py::test_tipos_numero_nulo_y_frontera` | Falla igual en `origin/feat/tercer-parcial`, sin ningún cambio de esta rama | Bloque A |

No se taparon: se reportan para que las corrija su dueño.

## Lo que se salta, y por qué

- Las pruebas de contenedores (`microservicios/pruebas_integracion/contenedores`) piden el compose levantado: se corren con `python infra/pruebas_integracion.py`.
- `test_mongo_real.py` pide `MONGO_URL_PRUEBAS`.
- Las de `abm-gpu` piden una GPU de NVIDIA.
- En `test_interoperabilidad.py`, la parte «sin token» de las rutas públicas.

## Cómo repetirla

1. Levanta un PostgreSQL 16 vacío y crea el rol `epidemia_app` (paso de usuarios de `docs/INSTALACION.md`).
2. Con `DATABASE_URL` apuntando a él, corre `python datos/scripts/prepara_base_pruebas.py --superusuario postgres --si`.
3. Desde la raíz, corre `python -m pytest backend_web frontend_web microservicios procesamiento frontend_desktop`.

Las pruebas de la web hablan con los servicios reales en el mismo proceso (`PuenteServicios` de `frontend_web/tests/base.py`).
