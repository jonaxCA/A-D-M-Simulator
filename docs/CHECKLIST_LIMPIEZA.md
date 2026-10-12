Revisé el repo con herramientas y leyendo los archivos más grandes. Usé vulture para buscar código muerto, pylint para duplicados, ruff (un *linter*, que revisa el código sin ejecutarlo) y radon para medir complejidad.

El repo tiene menos "basura" de la que sugiere su tamaño. Las 119 funciones de `queries.py` se usan todas, todas las plantillas están referenciadas, el CSS casi no tiene clases huérfanas y el linter solo encontró 6 imports sin usar. El problema real está concentrado en pocos lugares, y casi todo es **duplicación y desorden**, no código inútil.

Propongo tres fases, de menor a mayor riesgo. Cada una iría en PRs chicos y con las pruebas pasando.

## Fase 1: borrar lo que sobra (riesgo bajo)

Ya se completó esta fase. Medida con git sobre sus commits (`a911b3e..94a9c0c`), quitó 501
líneas y agregó 124:

- 444 de las borradas son los dos documentos obsoletos, `CHECKLIST_SEGUNDO_AVANCE.md` y
  `revision_bloques_E_F.md`.
- Casi todas las agregadas son el `AGENTS.md` de la raíz y este checklist.

## Fase 2: consolidar duplicados (≈250–400 líneas, riesgo medio)

1. **Auditoría repetida.** Hay 9 copias escritas a mano de `INSERT INTO audit_log` (1 en `audit.py` y 8 en `queries.py`), aunque ya existen `log_audit` y `_auditar`. Propongo dejar una sola función en `audit.py`.
2. **Flask metido en la capa de datos.** `queries.py` importa `flask.request` dentro de varias funciones para obtener la IP y el navegador. Ya existen `_ip()` y `_ua()`, pero tres funciones copian esa lógica en línea. Lo correcto es que la ruta reciba la IP y el *user agent* (el texto que identifica al navegador) y los pase como parámetros. Además de reducir código, esto es lo que les permitirá separar microservicios después, que es la razón de mantener la capa de repositorio.
3. **Parseo de formularios disperso.** En `queries.py` están `_entero`, `_entero_en_rango`, `_decimal`, `_numero` y `_fecha`. En `routes.py` están `_seed_desde_form` y `_esperado`. El bucle que limpia una lista de ids está copiado en `queries.py` y `simulaciones.py`.
   - El docstring de `_entero_en_rango` lo admite: se creó porque chocaba de nombre con `_entero` y hacía fallar `/reportes/nuevo`.
   - Se repartió en dos lugares. Lo que lee la petición (`_seed_desde_form`, `_esperado` y la lista de ids) va en `frontend_web/app/formularios.py`. Convertir texto a número o fecha va en `backend_web/conversion.py`, porque lo usan las validaciones del backend y una API también lo necesitaría. Si todo se hubiera ido al frontend, el backend terminaría importando del frontend.
4. **Exportaciones CSV.** Las tres repiten el mismo bloque (StringIO, writer, cabeceras HTTP). Se reemplaza por un helper `_csv(nombre, encabezados, filas)`.
5. **Boilerplate en pruebas.** El *boilerplate* es código de preparación que se copia igual en muchos lados. Siete archivos de `frontend_web/tests` repiten lo mismo: crear la app, simular `usuario_vigente` y armar un token. Propongo una clase base en `tests/base.py`. No se borra ninguna prueba; las 299 se quedan.

## Fase 3: reordenar (baja poco LOC, pero es lo que más ensucia)

1. **`queries.py`: arreglar lo que estorba, sin partirlo completo.** Tiene 3,919 líneas, pero ya está ordenado por pantalla y 80 de sus 113 funciones son consultas SQL directas. Partirlo movería 127 llamadas de `routes.py`, 25 archivos de pruebas y 22 `patch(...)` sin cambiar nada de lo que hace, y un `patch` que deja de interceptar una función mudada falla en silencio. Lo que sí estorba se ataca por partes:
   - Sacar los textos de pantalla (nombres de meses, etiquetas de estados, descripciones de eventos) a `frontend_web`, una pantalla por PR. Es lo que va contra su propia regla de que el formato viva en `frontend_web`, y lo que le estorbaría a una API. De paso se rompe el ciclo de importación con `simulaciones.py`.
   - Subir los imports al principio del archivo y hacer pública `_serializa`.
   - Partir `actualiza_grupos_edad_municipio`, la única función realmente enredada (complejidad 32).
   - Que lo nuevo no entre a `queries.py`; ya es regla en `backend_web/AGENTS.md`.
   - Extraer un dominio a su propio módulo solo cuando se construya su API, con `queries.py` como fachada para que nada se rompa. Los dominios casi coinciden con los microservicios planeados, así que el corte sigue sirviendo, pero cuando haga falta.
2. **`resolver()` en `motor/parametros.py` tiene complejidad ciclomática 103.** Esa métrica cuenta los caminos distintos que puede tomar una función: cada `if`, `for` o `and` suma uno, y arriba de ~20 ya cuesta probarla. Propongo partirla en un validador por bloque: población, edad desconocida, enfermedad e intervenciones.
3. **Comentarios "de historia".** Unos 50 comentarios cuentan cómo era el código antes o en qué bloque se hizo ("Bloque D", "antes…", "dejaba…"). Un comentario debe explicar por qué el código es como es hoy; la historia va en el mensaje del commit.
