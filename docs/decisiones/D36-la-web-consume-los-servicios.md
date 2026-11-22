# D36 - La web consume los microservicios

Fecha: 2026-11-19 · Estado: Aceptada · Reemplaza a D20 y D33

## Contexto
La retroalimentación del segundo parcial pide que ninguna aplicación cliente se conecte directo a PostgreSQL, MongoDB ni Redis, y que se compruebe que una operación de la web consume realmente una API. Hoy la web va directo a PostgreSQL (D20) y a Redis (D33), e importa `epidemia_comun`. D20 se tomó para que la web funcionara por su cuenta. La retroalimentación manda sobre esa razón (checklist, «Qué manda»).

## Opciones consideradas
- Opción A: la web sigue directa a la base y solo algunas pantallas llaman a los servicios.
- Opción B: la web pasa por completo a los servicios, módulo por módulo, sin respaldo en la base.
- Opción C: igual que B, pero cada pantalla regresa a PostgreSQL cuando su servicio no responde.

## Decisión
Opción B. La opción A no cumple la retroalimentación. La C deja las credenciales en la web y dos caminos al mismo dato, que es justo lo que se corrige.

**Cómo llama la web:**
- `backend_web` se queda como la capa de la web, pero sus funciones dejan de leer la base y llaman por HTTP al servicio dueño. Conservan su nombre y la forma de lo que regresan, así `frontend_web` casi no cambia.
- El cliente HTTP es propio de la web (`backend_web/servicios.py`, con `requests`). Pide JSON (`?format=json`), reenvía el JWT de la sesión (D34) y manda `X-Correlation-ID`. Espera 5 s.
- La web no importa `epidemia_comun`.
- La URL de cada servicio sale de `SERVICIO_<NOMBRE>_URL`. Si no viene, se usa `http://localhost:<puerto del catálogo>`. Detrás de nginx (D25) apunta a `https://<dominio>/<servicio>`.
- La web no reintenta escrituras.

**Sesión:**
- Iniciar sesión es `POST` a `auth`. La web guarda en su cookie firmada el token y el *refresh*, nunca la contraseña.
- Cerrar sesión revoca en `auth` y `sesiones`.
- La web ya no lee Redis. La validez de la sesión la decide cada servicio en cada llamada: un 401 manda a iniciar sesión de nuevo.

**Orden en que pasan los módulos.** Sigue la demostración integrada, para que se pueda demostrar cuanto antes:
1. Sesión: `auth` y `sesiones` (paso 1).
2. Escenarios, versiones y aprobación: `escenarios` y `aprobacion` (paso 5).
3. Corridas y resultados: `corridas` y `resultados` (paso 8).
4. Comparación y frontera: `comparacion` y `pareto` (pasos 9 y 10).
5. Tablero y mapa: `indicadores`, `series`, `zonas` y `casos` (lectura).
6. Catálogos: `enfermedades`, `parametros`, `regiones`, `poblacion` y `tipos-intervencion`.
7. Administración: `usuarios`, `roles`, `notificaciones` y la consulta de la bitácora (E7).

**Cuando un servicio no responde** (caída, tiempo agotado o 5xx):
- La sección que depende de él muestra «Este dato no está disponible por ahora (servicio `<nombre>`). Intenta de nuevo en unos minutos.» y lo demás de la página se ve.
- En un formulario, el mensaje dice que el cambio **no** se guardó.
- Un 403 se muestra como acceso denegado, y un 401 manda a iniciar sesión.
- Nunca se muestra la traza.
- Si cae `auth`, no se puede entrar. Si caen `sesiones` o Redis, los servicios responden 503 y la web muestra el aviso en toda pantalla protegida: la web falla cerrada, igual que los servicios (regla 8 de `microservicios/AGENTS.md`).

**Bitácora:** la escribe el servicio que hace el cambio, con el contexto del token. La web deja de llamar a `log_audit`.

## Consecuencias
- Un solo camino a cada dato y a cada regla, el de su servicio. Esto habilita D37.
- La web pierde la independencia que daba D20: sin servicios no funciona. Se acepta porque la retroalimentación lo pide, y se compensa con la demostración de fallos (cada pantalla explica qué falta).
- Desaparece el riesgo aceptado de D33: con Redis caído ya no se aceptan sesiones sin poder revisar su revocación.
- Cada pantalla que pasa necesita una ruta en su servicio. Lo que falte se pide al bloque dueño (E9), a partir del inventario de C6.
- Al terminar, el `.env` de la web solo trae `SECRET_KEY` y las URL de los servicios, sin credenciales de PostgreSQL, MongoDB ni Redis (C6).
- Las pruebas de la web simulan las respuestas HTTP de los servicios en lugar de usar la base de pruebas.
