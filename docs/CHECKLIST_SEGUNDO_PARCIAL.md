# EPIDEMIA — Checklist del segundo parcial (propuesta)

Objetivo: construir una **arquitectura distribuida** de 26 microservicios pequeños, cada uno
con una sola tarea. Hablan JSON y XML, comparten la sesión por Redis, se autentican con JWT,
publican sus contratos y corren **cada uno en su contenedor de Docker**.

- Los servicios son para las **apps de escritorio (XML) y móvil (JSON)**.
- El **sistema web** (el monolito) sigue hablando directo con PostgreSQL.
- Para comprobar que los servicios funcionan hay una **consola** web tipo Swagger/Postman.

Stack de esta etapa: **PostgreSQL + Redis + microservicios Flask en Docker + monolito
web.** Se sigue el patrón de la librería vista en clase: biblioteca común, XML por defecto,
Swagger en `/docs` y un rol de base por servicio. Nada de MongoDB, Cloud Storage, nginx ni
CUDA.

Qué hace cada servicio, qué tablas escribe y lee, a quién llama y en qué puerto escucha está
en [`docs/arquitectura/microservicios.md`](arquitectura/microservicios.md). Este checklist
son las tareas.

> Propuesta para repartir temprano. Cada bloque tiene un responsable y un revisor, y cada
> casilla debería ser un issue, una rama y un Pull Request. Las decisiones de esta etapa
> ya están tomadas: están en el bloque 0 y en `docs/decisiones.md`.

> **Avance al 21 de octubre** (en `2do-parcial-gpo-10am`): los 26 servicios, con la
> biblioteca común, Redis, Docker y las migraciones 026 a 030. Pasan las 1,294 pruebas
> (monolito, motor y servicios) en un solo `pytest`, con la base de pruebas rehecha después
> de la 029 (`prepara_base_pruebas.py`). Ningún servicio cumple todavía la definición de
> terminado: faltan la consola y las pruebas de integración contra los contenedores.
> Las casillas de escenarios y vigilancia las marcó quien hizo esos servicios; las demás se
> revisaron contra el código.

---

## Reparto propuesto

| Integrante | Servicios                                                                                    | Bloques transversales                                               | Días aprox. | Revisa a |
|------------|----------------------------------------------------------------------------------------------|---------------------------------------------------------------------|-------------|----------|
| 1          | `auth`, `sesiones`                                                                           | **A** Biblioteca común y plantilla · **L** Seguridad                | 10.5        | 2        |
| 2          | `usuarios`, `roles`, `regiones`, `poblacion`, `zonas`, `series`                              | **K** Redis                                                         | 10          | 1        |
| 3          | `enfermedades`, `parametros`, `tipos-intervencion`, `casos`, `sincronizacion`, `indicadores` | **N** Sistema web · **P** Documentación                             | 9.75        | 6        |
| 4          | `escenarios`, `intervenciones`, `aprobacion`, `validacion`, `escenarios-xml`                 | —                                                                   | 9.5         | 5        |
| 5          | `corridas`, `simulador`, `resultados`, `comparacion`, `pareto`, `notificaciones`             | —                                                                   | 10          | 4        |
| 6          | `estado-servicios`                                                                           | **I** Consola · **J** Docker · **M** Contratos · **O2** Integración | 10.5        | 3        |

- El reparto se equilibra **por esfuerzo, no por número de servicios**. Un servicio de solo
  lectura (`regiones`) es medio día; uno con reglas y llamadas a otros (`escenarios-xml`) son
  dos o tres. Suma unos 60 días de trabajo contra 60 disponibles: no hay holgura, por eso los
  servicios opcionales del catálogo quedan fuera.
- Cada quien escribe las pruebas unitarias, el contrato y el README de sus servicios. Eso es
  parte de la definición de terminado, no un bloque aparte.
- Por qué estas parejas de revisión:
  - **1 y 2:** el token que emite `auth` es el que verifica la biblioteca común, y
    `usuarios` y `roles` cierran sesiones con `sesiones`.
  - **4 y 5:** solo se simula una versión aprobada.
  - **3 y 6:** `sincronizacion` y `casos` son lo que más va a ejercitar la consola.
- **Ruta crítica:** la biblioteca común con la plantilla (integrante 1) y la imagen base de
  Docker (integrante 6). Hasta el día 3, los demás escriben el borrador del contrato de sus
  servicios y el mapa de las funciones de `backend_web` que van a usar.

## Calendario (diez días hábiles)

| Días             | Qué                                                                                                                                               |
|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| 1                | Bloque 0 completo. El integrante 6 arranca la imagen base y agrega PostgreSQL al compose, que ya trae Redis; el integrante 1, la biblioteca común |
| 2–3              | Biblioteca mínima (A1–A4) y plantilla (A6). Los demás: borrador de OpenAPI y mapa de funciones de sus servicios                                   |
| **3 · Hito 0**   | Cada quien genera sus servicios con la plantilla, y los 26 contenedores responden `/health`                                                       |
| **5 · Hito 1**   | `auth` emite tokens y cada servicio responde **un GET protegido** en XML y en JSON, con Swagger. La consola lista los 26 servicios y su salud     |
| 6–8              | Escrituras, llamadas entre servicios, cola del simulador, XSD y el probador de la consola                                                         |
| 9                | Pruebas de integración y guion de aceptación completo, corrido desde la consola                                                                   |
| **10 · Entrega** | Congelamiento, evidencias y `.tar.gz`                                                                                                             |

**Si el tiempo no alcanza, el orden de recorte es este** (los imprescindibles cubren los diez
entregables):

1. **Imprescindibles:**
   - servicios: `auth`, `sesiones`, `usuarios`, `enfermedades`, `regiones`, `casos`,
     `escenarios`, `validacion`, `aprobacion`, `escenarios-xml`, `corridas`, `simulador`,
     `resultados` y `estado-servicios`;
   - además: la consola, Docker y Redis.
2. **Después:** `roles`, `parametros`, `poblacion`, `tipos-intervencion`, `intervenciones`,
   `sincronizacion` y `notificaciones`.
3. **Al final:** `comparacion`, `pareto`, `indicadores`, `series` y `zonas`.

---

## 0. Organización y decisiones (todo el equipo, día 1)

### Repositorio y flujo
- [x] Una rama de integración, `segundo-parcial`, de la que salen todas las ramas de trabajo
      (es `feat/segundo-parcial-grupo-2pm`)
- [ ] Crear un issue por casilla de este documento, con responsable y etiqueta de bloque o
      de servicio
- [ ] Una rama por issue y todo por Pull Request revisado por la pareja asignada
- [x] Los `.env` nunca entran al repositorio; solo `.env.example` y `.env.shared.example`
- [ ] El `.tar.gz` de entrega incluye la carpeta `.git`

### Decidido (cada decisión queda anotada en `docs/decisiones.md`)
- [x] Docker: un contenedor por microservicio (ya no es opcional)
- [x] Los microservicios solo los usan las apps; el monolito no los consume
- [x] El catálogo de `docs/arquitectura/microservicios.md` es la referencia. Si un servicio
      cambia de tarea, de tablas o de puerto, se cambia ahí primero
- [x] Formato: el de clase, XML por defecto y JSON con `?format=json`. También se acepta
      `Accept: application/json`; si los dos chocan, manda `?format`
- [x] Entregas: en este parcial, los 26 servicios con sus contratos; las apps de escritorio
      y móvil, en el tercer parcial. Mientras tanto, la consola hace sus veces
- [x] Rutas en inglés, como en la arquitectura y en el catálogo (`/api/v1/scenarios`)
- [x] Nombres de los servicios en español, los del catálogo (`escenarios`, `corridas`…)
- [x] Sin `pasarela`: las apps y la consola piden la URL de cada servicio al directorio de
      `estado-servicios`
- [x] Pruebas de los servicios con `pytest`, que también corre las 431 actuales de `unittest`
- [x] Validación de XSD con `xmlschema` y lectura de XML con `defusedxml`, como en clase
- [x] Migraciones de esta etapa reservadas: 026 en adelante (regla de `datos/AGENTS.md`)

### Estructura acordada
- [ ] `microservicios/comun/` (paquete `epidemia_comun`), `microservicios/<servicio>/` para
      los 26 y `microservicios/consola/`
- [x] `infra/docker/` con la imagen base y `infra/docker-compose.yml`
- [x] `docs/contratos/<servicio>/` con `openapi.json`, ejemplos y, si aplica, su `.xsd`
- [x] Llenar `microservicios/AGENTS.md`, que hoy está vacío, con las reglas de este documento

---

## A. Biblioteca común y plantilla · Integrante 1

Lo que los 26 repiten vive aquí una sola vez. La `libreria_comun` de clase sirve de
referencia.

### A1. Arranque y configuración
- [x] `ajustes`: lee `.env.shared` (JWT, Redis, audiencia, TTL) y el `.env` del servicio. Las
      variables de entorno del contenedor tienen prioridad
- [x] Falla al arrancar si falta un secreto o se queda con el valor de ejemplo, igual que hoy
      `secreto_jwt()`
- [x] `crear_app(nombre, contrato)`: registra errores, `/health`, `/docs`, `/openapi.json`,
      CORS y el registro de peticiones
- [x] Arranque con waitress en el puerto 8000 dentro del contenedor

### A2. Formatos
- [x] `responder(datos, raiz)`: XML por defecto y JSON con `?format=json` o con
      `Accept: application/json`; si los dos chocan, manda `?format`
- [x] Un valor desconocido de `?format` es error 400, no el formato por omisión. Un `Accept`
      distinto de `application/json` (como el `text/html` de un navegador) se ignora y se
      responde XML
- [x] Nombres singulares para los elementos de las colecciones (`escenarios` → `escenario`)
- [x] `leer_cuerpo()`: acepta JSON o XML según el `Content-Type`, con `defusedxml` y límite de
      tamaño
- [x] Fechas en ISO 8601 y `Decimal` como número en los dos formatos

### A3. Errores
- [x] Errores RFC 7807 (`application/problem+json` y `application/problem+xml`) con un
      `codigo` estable: `TOKEN_AUSENTE`, `TOKEN_REVOCADO`, `PERMISO_INSUFICIENTE`,
      `NO_ENCONTRADO`, `CONFLICTO`, `DATOS_INVALIDOS`, `SERVICIO_NO_DISPONIBLE`…
- [ ] Tabla única de códigos HTTP: 400, 401, 403, 404, 409, 422, 503 y 500
- [x] Un 500 no expone la traza ni el SQL

### A4. Verificación de tokens
- [x] `@requiere_token(roles=...)` revisa, en este orden:
  - [x] `Authorization: Bearer`;
  - [x] `alg=HS256` (rechaza `none`);
  - [x] firma;
  - [x] `iss`, `aud`, `exp` y `nbf`;
  - [x] que no esté revocado ni su sesión cerrada (`sesiones.verificar()`);
  - [x] el rol.
- [x] `@solo_servicios`: para las rutas internas, acepta solo un token de servicio
- [x] Del token sale el `Contexto` (usuario, IP, user agent) que ya usan las funciones que
      auditan
- [x] Si Redis está caído, una ruta protegida responde 503 y nunca deja pasar

### A5. Salud, Swagger y registro
- [x] `/health` en XML y JSON, con el estado de PostgreSQL y de Redis
      (`redis_compartido.estado()`) y la versión del servicio
- [x] `/openapi.json` servido desde el contrato del servicio y Swagger UI en `/docs`
- [x] Cada petición se registra con método, ruta, código, duración, usuario y un
      `X-Correlation-ID`

### A6. Plantilla de servicio (lista el día 3)
- [ ] `scripts/nuevo_servicio.py <nombre> <puerto>` genera:
      *Avance (19 oct): su `Dockerfile` ya es como los demás; falta que agregue el servicio
      al compose y que genere la prueba de `/health`.*
  - [x] la carpeta, con `app.py`, `rutas.py` y `README.md`;
  - [ ] el `Dockerfile` y su entrada en el compose;
  - [x] el esqueleto de `openapi.json`;
  - [ ] una prueba de `/health`.
- [ ] Un servicio recién generado ya responde `/health`, `/docs` y `/openapi.json` en su
      contenedor

### A7. Cliente entre servicios
- [x] `llamar(servicio, metodo, ruta, formato="json"|"xml", cuerpo=None)` resuelve la URL,
      reenvía el token de la persona o usa uno de servicio, y propaga el `X-Correlation-ID`
- [x] Tiempo de espera; un servicio caído se convierte en 503 `SERVICIO_NO_DISPONIBLE`, no en
      un 500
- [ ] Pruebas de la biblioteca: formatos, errores, cada caso de rechazo de token, Redis caído
      y el cliente con un servicio que no responde

---

## Definición de terminado de un servicio

Vale para los 26. Cada servicio de los bloques B a H tiene una casilla que la remite.

- [ ] Generado con la plantilla y en el puerto del catálogo
- [ ] Responde XML por defecto y JSON con `?format=json` o `Accept: application/json`, y
      acepta cuerpos en los dos formatos
- [ ] `/health`, `/docs` (Swagger) y `/openapi.json`
- [ ] Errores RFC 7807 en los dos formatos
- [ ] Rutas protegidas con los mismos roles que la pantalla equivalente del monolito
- [ ] Su rol de PostgreSQL solo puede escribir lo que el catálogo dice que escribe
- [ ] Toda escritura queda en la bitácora, dentro de la misma transacción
- [ ] Contenedor propio con *healthcheck*, en el compose
- [ ] Contrato en `docs/contratos/<servicio>/`: `openapi.json`, un ejemplo JSON y uno XML por
      ruta, y el `.xsd` si su recurso lo tiene
- [ ] Pruebas unitarias, con la base y Redis simulados, y al menos una de integración contra
      el contenedor
- [ ] README: qué hace, rutas, roles, variables y cómo probarlo
- [ ] Aparece en `estado-servicios` y en la consola

---

## B. Identidad y acceso

Base existente: `backend_web/auth.py` (bcrypt, bloqueo tras cinco intentos, revalidación de
la cuenta) y el CRUD de usuarios de `routes.py`.

### B1. `auth` · Integrante 1
- [x] Login con el bloqueo por intentos y la bitácora (`LOGIN` / `LOGIN_FAILED`) de hoy
- [x] Emite el *access* (20 min) y el *refresh*, y abre la sesión en Redis
      (`sesiones.abrir()`)
- [x] Claims: `iss`, `aud`, `sub`, `roles`, `sid`, `jti`, `iat`, `nbf`, `exp`
- [x] Una cuenta inactiva o bloqueada recibe el mismo mensaje que una contraseña equivocada
- [ ] Cumple la definición de terminado

### B2. `sesiones` · Integrante 1
- [x] `refresh` rota el *refresh*; uno ya usado cierra la sesión completa
      (`sesiones.renovar()`)
- [x] `logout` revoca el *access* y cierra la sesión (`sesiones.revocar()` y `cerrar()`)
- [x] `current` dice quién soy, mis roles y cuándo vence la sesión
- [x] Ruta interna para cerrar todas las sesiones de una cuenta (la usan `usuarios` y `roles`),
      con `sesiones.cerrar_todas()`
- [ ] Cumple la definición de terminado

### B3. `usuarios` · Integrante 2
- [x] Alta, consulta, edición, activar y desactivar (solo ADMINISTRADOR)
- [x] Eliminar solo sin dependencias (`dependencias_usuario`); con ellas, 409
- [x] Al desactivar una cuenta, llama a `sesiones` para cerrar las suyas
- [x] Nunca devuelve ni audita `password_hash`
- [ ] Cumple la definición de terminado

### B4. `roles` · Integrante 2
- [x] Roles y sus permisos (`permissions`, `role_permissions`)
- [x] Asignar o quitar roles a una cuenta. Al quitar uno, llama a `sesiones`
- [ ] Cumple la definición de terminado

---

## C. Catálogos

### C1. `enfermedades` · Integrante 3
- [x] Listado con búsqueda, filtros y paginación, como la pantalla
- [x] Alta y edición (EPIDEMIOLOGO y ADMINISTRADOR); el código no se edita
- [x] Activar y desactivar como baja lógica, nunca `DELETE`
- [ ] Cumple la definición de terminado

### C2. `parametros` · Integrante 3
- [x] Los seis parámetros con valor, fuente y marca de supuesto
- [x] No se guarda un parámetro sin fuente ni marca de supuesto
- [x] El estado: simulable, cuáles faltan y cuáles son supuestos
- [x] Solo escribe la columna `default_params` (permiso por columna)
- [ ] Cumple la definición de terminado

### C3. `regiones` · Integrante 2
- [x] Nuevo León y sus 51 municipios, con la fuente de cada cifra como dato (`tipo`,
      `fuente`…), no como texto
- [x] Responde aunque Redis esté caído
- [ ] Cumple la definición de terminado

### C4. `poblacion` · Integrante 2
- [x] Corrección de la población (ADMINISTRADOR), con el control de concurrencia de hoy
      (valor esperado)
- [x] Bandas de edad: consulta y corrección (los pasos de LIMP-11c)
- [ ] Cumple la definición de terminado

### C5. `tipos-intervencion` · Integrante 3
- [x] Los tipos con su `param_schema`
- [ ] Cumple la definición de terminado

---

## D. Vigilancia

### D1. `casos` · Integrante 3
- [x] Alta con las validaciones de hoy (`valida_caso`, catálogo vigente, fechas)
- [x] Consulta con filtros y un caso por id
- [ ] Cumple la definición de terminado

### D2. `sincronizacion` · Integrante 3
- [x] Recibe un lote de casos de la app móvil y manda cada uno a `casos`, en JSON
- [x] El mismo lote enviado dos veces no duplica casos (Redis, `sync:lote:<id>`)
- [x] Regresa el resultado de cada caso: creado, duplicado o rechazado con su error
- [x] Consulta del resultado de un lote ya enviado
- [ ] Cumple la definición de terminado

---

## E. Escenarios · Integrante 4

### E1. `escenarios`
- [x] Alta: escenario y versión 1 en una sola transacción, después de pasar por `validacion`
- [x] Consulta, listado e historial de versiones
- [x] Versión siguiente (nunca sobrescribe) y duplicado
- [x] Acepta el escenario en XML (lo usa `escenarios-xml`)
- [ ] Cumple la definición de terminado

### E2. `intervenciones`
- [x] Agregar, quitar y reordenar mientras la versión es borrador; si no lo es, 409
- [x] Parámetros validados contra el `param_schema` del tipo
- [x] Costo de la intervención
- [ ] Cumple la definición de terminado

### E3. `aprobacion`
- [x] Enviar a revisión, después de pasar por `validacion`
- [x] Aprobar o rechazar, con motivo obligatorio para rechazar
- [x] Nadie revisa su propia versión: 409 con mensaje claro, además del CHECK de la base
- [x] Si otra persona cambió el estado mientras tanto, 409 (control de concurrencia de hoy)
- [x] Bandeja de pendientes de revisión
- [x] Al aprobar, avisa con `notificaciones` (best-effort, con token de servicio y tipo
      `SCENARIO_APPROVED`, que agrega la migración 029)
- [x] Solo escribe las columnas de estado y revisión de `scenario_versions` (permiso por
      columna)
- [ ] Cumple la definición de terminado

### E4. `validacion`
- [x] Recibe un escenario y regresa errores y **avisos** del motor, sin guardar nada
- [x] Valida una versión guardada por su id
- [ ] Cumple la definición de terminado

### E5. `escenarios-xml`
- [x] Exporta el escenario completo (versión, población por edad, intervenciones) en XML
- [x] Publica su XSD en `/api/v1/schemas/scenario.xsd`
- [x] Importa un XML: lo valida contra el XSD, luego con `validacion`, y crea el escenario con
      `escenarios` (le manda el XML) y las intervenciones con `intervenciones`
- [x] Un XML inválido regresa 422 con el detalle de la validación
- [x] Exportar e importar da la misma versión (prueba de ida y vuelta)
- [ ] Cumple la definición de terminado

---

## F. Simulación · Integrante 5

### F1. `corridas`
- [x] Lanzar una corrida solo sobre una versión aprobada: crea el lote y la corrida, la mete
      en la cola de Redis (`cola.encolar()`) y responde 202 con su id
- [x] Semilla opcional; `forzar_error` solo para ADMINISTRADOR, como hoy
- [x] Candado en Redis (`candados.candado(llaves.candado_corrida(version), ttl)`) para que un doble clic no lance dos corridas
- [x] Estado y progreso (leídos de Redis y de PostgreSQL), y cancelar una corrida encolada
- [ ] Cumple la definición de terminado

### F2. `simulador`
- [x] Proceso trabajador: toma corridas de `queue:simulaciones` y ejecuta el motor
- [x] Escribe el progreso en `job:<id>:progress` y el estado final y los resultados en
      PostgreSQL
- [x] Al arrancar, cierra como fallidas las corridas que quedaron a medias (solo las de
      `ejecutando`: las encoladas siguen en la cola)
- [x] Al terminar o fallar, avisa con `notificaciones` usando un token de servicio
- [x] Varios contenedores de `simulador` no toman la misma corrida (transición condicionada)
- [ ] Cumple la definición de terminado

### F3. `resultados`
- [x] Curvas e indicadores de una corrida, con caché en Redis cuando ya terminó
- [x] El aviso de que los resultados no son una predicción viaja en la respuesta
- [ ] Cumple la definición de terminado

### F4. `comparacion`
- [x] Tabla comparativa y curvas superpuestas de varias corridas
- [ ] Cumple la definición de terminado

### F5. `pareto`
- [x] Costo contra impacto y frontera de Pareto. Lee los resultados directo de la base
      mientras no exista `resultados` (ver la nota del catálogo)
- [ ] Cumple la definición de terminado

---

## G. Analítica

### G1. `indicadores` · Integrante 3
- [x] Indicadores del tablero y resumen de situación, con caché en Redis
- [ ] Cumple la definición de terminado

### G2. `series` · Integrante 2
- [x] Curva epidémica y series por edad, sexo y totales, con los filtros de Monitoreo
- [ ] Cumple la definición de terminado

### G3. `zonas` · Integrante 2
- [x] Datos del mapa por municipio y detalle por zona (variación, semáforo, zonas en riesgo)
- [x] El texto de "mayor cambio" sigue la regla de LIMP-20: todas las zonas, orden fijo
- [ ] Cumple la definición de terminado

---

## H. Plataforma

### H1. `notificaciones` · Integrante 5
- [x] Las notificaciones de quien consulta, y marcar como leída
- [x] Ruta interna, solo con token de servicio, para crearlas (`simulador`, `aprobacion`)
- [ ] Cumple la definición de terminado

### H2. `estado-servicios` · Integrante 6
- [x] Directorio: nombre, URL, versión y enlace a `/docs` de los 26
- [x] Sondea el `/health` de cada uno **en XML** cada pocos segundos y guarda el último estado
      y un historial corto en Redis
- [x] Un servicio caído aparece en rojo con la causa (base, Redis o el proceso)
      *`estado-servicios` da el estado y la causa (`causas`); el rojo lo pinta la consola
      (bloque I).*
- [ ] Cumple la definición de terminado

---

## I. Consola de pruebas (tipo Swagger/Postman) · Integrante 6

Es la página para comprobar que los 26 funcionan. Sustituye a la app mientras no exista, y
es la herramienta del guion de aceptación.

- [ ] Contenedor `consola` en el puerto 5260
- [ ] Panel de salud con los 26 servicios: estado, versión y latencia, leídos de
      `estado-servicios`. Se actualiza solo
- [ ] Swagger UI con un selector de los 26 contratos, y "Try it out" funcionando (CORS
      abierto solo para el origen de la consola)
- [ ] Iniciar sesión desde la consola: pide el token a `auth` y lo pone como `Bearer` en
      Swagger y en el probador. El token vive en la memoria de la página, no en
      `localStorage`, y cerrar sesión llama a `sesiones`
- [ ] Probador tipo Postman:
  - [ ] elegir servicio, método y ruta;
  - [ ] cuerpo en JSON o en XML;
  - [ ] pedir la respuesta en JSON o en XML;
  - [ ] ver código, tiempo, cabeceras (con el `X-Correlation-ID`) y el cuerpo con formato.
- [ ] Recorrido de aceptación: los pasos del guion como peticiones listas para correr en
      orden, que guardan los ids que devuelve cada paso
- [ ] Exportar una petición como comando `curl`, con el token oculto
- [ ] Nunca muestra contraseñas; los tokens aparecen recortados
- [ ] Funciona contra los contenedores o contra servicios corriendo fuera de Docker (URL base
      configurable)

---

## J. Docker: un contenedor por servicio · Integrante 6

- [x] `infra/docker/base.Dockerfile`: `python:3.12-slim`, usuario no root y las dependencias
      de `epidemia_comun`, `backend_web` y `procesamiento`. Imagen `epidemia/base`
- [x] Un `Dockerfile` por servicio: parte de `epidemia/base`, copia su carpeta, arranca en el
      puerto 8000 y tiene `HEALTHCHECK` a `/health`
- [ ] `infra/docker-compose.yml` con:
  - [x] PostgreSQL, con volumen e inicialización: dump, semillas y migraciones 026 en
        adelante;
  - [x] Redis, con contraseña y AOF (lo hizo el bloque K);
  - [ ] los 26 servicios y la consola (van los 26; falta la consola);
  - [x] `depends_on` con `condition: service_healthy`.
- [x] Perfiles del compose por dominio (`identidad`, `catalogos`, `escenarios`…), para
      levantar solo una parte en máquinas con poca memoria
- [x] Red interna. Solo se publican los puertos del catálogo; PostgreSQL y Redis no quedan
      expuestos fuera de la máquina
- [x] Secretos en el `.env` del compose (sin versionar), con su `.env.example`
- [x] `docker compose up` desde cero levanta todo, con los 26 *healthchecks* en verde
      *(21 oct): los 26, PostgreSQL y Redis en verde en unos 3.5 min, construyendo las
      imágenes; ninguna ruta GET da 500 con las tres cuentas de la demostración. La consola
      se suma cuando exista.*
- [x] Reconstruir y reiniciar un servicio no toca a los demás
- [x] Medir la memoria con todo arriba y anotarla en la guía (con los 26, unos 1,100 MiB)
- [x] `docs/INSTALACION.md`: sección de Docker, desde cero

---

## K. Redis en operación · Integrante 2

La capa de Redis de la biblioteca común y el contenedor se adelantaron antes del día 1. Su uso
está en [`microservicios/comun/README.md`](../microservicios/comun/README.md).

### K0. Módulo de Redis de `epidemia_comun` (listo)
- [x] Cliente compartido con tiempos de espera cortos:
  - [x] `requerido()` falla cerrado, con 503;
  - [x] `opcional()` deja seguir con la base.
- [x] `sesiones`:
  - [x] abrir, renovar con *refresh* de un solo uso, cerrar y cerrar todas las de una cuenta;
  - [x] revocar y verificar en un solo viaje.
- [x] `cache` con TTL, que conserva `Decimal` y fechas
- [x] `candados` con NX y TTL; solo suelta el candado quien lo tomó
- [x] `cola` de corridas, con un cliente aparte para la espera bloqueante
- [x] `llaves.py` con las llaves del catálogo, y una prueba que revisa que coincidan con la
      tabla
- [x] 33 pruebas con fakeredis; también pasan contra el Redis del compose con
      `REDIS_URL_PRUEBAS`

### K1. En operación
- [x] Contenedor de Redis con `requirepass`, `appendonly yes` y `noeviction`, para que no se
      expulsen sesiones ni revocaciones (`infra/docker-compose.yml`, Redis 7.4). Probado:
      *healthcheck* en verde, rechaza conexiones sin contraseña, los datos sobreviven a un
      reinicio y las 33 pruebas pasan contra él
- [x] Tabla de llaves del catálogo con su TTL y su servicio dueño. Quien implemente
      `simulador`, `sincronizacion` y `estado-servicios` anota el TTL de sus llaves
- [x] En Redis se guarda la huella de los identificadores de sesión y de *refresh*, no el
      valor
- [x] Si Redis se cae, en los servicios (la biblioteca ya lo hace y lo prueba):
  - [x] lo protegido responde 503;
  - [x] los catálogos públicos siguen respondiendo;
  - [x] las cachés se reconstruyen solas al volver.
- [x] Prueba con Redis apagado: el login y las escrituras fallan con 503 y los catálogos
      responden

---

## L. Seguridad entre componentes · Integrante 1

- [ ] Un solo `JWT_SECRET_KEY` y una audiencia común (`epidemia-api`) en `.env.shared`
- [x] **Token de servicio** para las llamadas sin persona detrás: dura poco, tiene su propia
      audiencia (`epidemia-interno`) y solo lo aceptan las rutas internas
      (`epidemia_comun.seguridad.token_servicio()`, 60 s; lo usan `simulador` y `aprobacion`)
- [x] Cuando un servicio llama a otro por una persona, reenvía su token; nunca lo cambia por
      uno con más permisos
- [ ] Migración 026: un rol de PostgreSQL por servicio, generado desde una tabla de permisos.
      Lleva permisos por columna para `parametros`, `poblacion` y `aprobacion`, y ninguno usa
      `postgres`
      *Avance (21 oct): de la 026 a la 030 cubren los 26, con permisos por columna donde
      solo escriben una parte (`parametros`, `poblacion`, `aprobacion`, `corridas`,
      `simulador` y `notificaciones`). La 029 es de `corridas`, `simulador`, `resultados` y
      `notificaciones`, y la 030 de `estado-servicios`, que solo se conecta. Los permisos
      están escritos a mano, no generados desde una tabla.*
- [ ] Prueba de roles: `regiones` **no puede** escribir en `scenarios`, y `aprobacion` no
      puede cambiar el contenido de una versión
      *Avance (19 oct): comprobado a mano en el PostgreSQL del compose; falta como prueba
      automática (bloque O2).*
- [x] CORS cerrado: solo el origen de la consola
- [x] Pruebas negativas de token:
  - [x] `alg: none`;
  - [x] firma con otro secreto;
  - [x] vencido;
  - [x] otra audiencia;
  - [x] revocado;
  - [x] rol insuficiente;
  - [x] token de servicio en una ruta pública.
- [x] La bitácora registra el usuario y la IP también cuando la operación llega por la API
- [x] La IP de origen se toma de la conexión, y de `X-Forwarded-For` solo si viene de la red
      interna de Docker

---

## M. Contratos JSON, XML y XSD · Integrante 6 (cada responsable aporta el suyo)

- [ ] Los 26 `docs/contratos/<servicio>/openapi.json`, idénticos al que sirve cada
      `/openapi.json`. Una prueba lo compara
      *Avance (21 oct): 26 de 26. La prueba que los compara con lo servido cubre catálogos;
      los de identidad no tienen ejemplos JSON ni XML.*
- [ ] XSD de los recursos principales:
  - [ ] escenario completo;
  - [x] resultado de una corrida;
  - [x] enfermedad con sus parámetros;
  - [ ] caso;
  - [ ] lote de sincronización;
  - [x] el error (`problem+xml`).
- [ ] Prueba de contrato: cada ejemplo XML valida contra su XSD, y cada respuesta JSON contra
      su esquema del OpenAPI
- [x] Versionado: todo bajo `/api/v1/`; un cambio incompatible crea `/api/v2/`
- [ ] `docs/contratos/README.md`: cómo leer los contratos y dónde está cada uno

---

## N. Sistema web (monolito) · Integrante 3

El monolito no consume los servicios, pero comparte la base con ellos.

- [x] Sigue funcionando igual, ya sea con PostgreSQL local o con el del compose
- [x] Las migraciones de esta etapa (roles por servicio) no le quitan permisos a
      `epidemia_app`
- [x] Las 431 pruebas actuales siguen pasando
- [ ] (Opcional) Enlace a la consola desde el menú de ADMINISTRADOR

---

## O. Pruebas

### O1. Unitarias · cada responsable las de sus servicios
- [x] La biblioteca común: formatos, errores, tokens, Redis y el cliente entre servicios
- [ ] Cada servicio: validaciones, reglas y permisos, con la base y Redis simulados
- [x] El motor y las pruebas actuales siguen pasando

### O2. Integración · Integrante 6
- [ ] Un compose de pruebas sobre `simulador_epidemico_pruebas` y un Redis aparte, nunca sobre
      los de la demostración
- [ ] El flujo completo por HTTP: login → escenario → intervenciones → aprobación → corrida →
      resultados → comparación
- [ ] Llamadas entre servicios en XML: `escenarios-xml` → `escenarios`, y `estado-servicios` →
      `/health`
      *Avance (21 oct): `estado-servicios` ya sondea en XML. Probado a mano contra los
      contenedores: un servicio detenido sale `caido`, con Redis detenido los 26 salen
      `degradado` por Redis, y al volver Redis todo regresa sin reiniciar servicios. Falta
      como prueba automática.*
- [ ] Revocación entre servicios: logout en `sesiones` y el token rechazado en `escenarios`
- [ ] La cola: dos `simulador` y diez corridas; cada corrida se ejecuta una sola vez
- [ ] Redis apagado y encendido a mitad de la prueba
- [ ] El recorrido de la consola exportado como evidencia

---

## P. Documentación y evidencias · Integrante 3

- [x] `docs/arquitectura/arquitectura_v2.md`: lo que sí se construyó, a partir del catálogo,
      con un diagrama de servicios, Redis y PostgreSQL
- [ ] Revisar que cada servicio tenga su README (es parte de la definición de terminado)
- [ ] Actualizar `AGENTS.md`, `microservicios/AGENTS.md` y `docs/decisiones.md`
- [ ] Carpeta `evidencias/`:
  - [x] resultado de las pruebas;
  - [ ] el recorrido de aceptación de la consola;
  - [ ] capturas de Swagger y del panel de salud;
  - [ ] `docker compose ps` con todo en verde.
- [ ] Nada de secretos, tokens ni contraseñas en las evidencias

---

## Prueba de aceptación (guion de la revisión)

Correr completo, desde cero, desde la consola. Si los 22 pasos pasan, el parcial está
cumplido.

- [ ] 1. `docker compose up` desde cero: los 26 servicios, la consola, PostgreSQL y Redis en
      verde
- [ ] 2. En la consola, el panel de salud muestra los 26 en verde
- [ ] 3. `/health` de un servicio en XML (sin parámetro), en JSON con `?format=json` y en
      JSON con `Accept: application/json`
- [ ] 4. Abrir el Swagger de varios servicios desde el selector
- [ ] 5. Iniciar sesión como analista: recibir *access* y *refresh*
- [ ] 6. Consultar el catálogo de enfermedades en XML y en JSON
- [ ] 7. Registrar un caso, y un lote de sincronización enviado dos veces sin duplicar
- [ ] 8. Crear un escenario en JSON y agregarle intervenciones
- [ ] 9. Exportarlo en XML y validarlo contra su XSD
- [ ] 10. Importar un XML válido (crea el escenario) y uno inválido (422 con el detalle)
- [ ] 11. Enviar a revisión e intentar aprobarlo como el mismo analista: rechazado
- [ ] 12. Iniciar sesión como epidemiólogo y aprobarlo; aparece la notificación
- [ ] 13. Lanzar una simulación y seguir su progreso hasta COMPLETADA
- [ ] 14. Consultar resultados, comparar dos corridas y ver la frontera de Pareto
- [ ] 15. Renovar el token; reusar el *refresh* viejo cierra la sesión
- [ ] 16. Logout: el mismo token es rechazado por otro servicio (`TOKEN_REVOCADO`)
- [ ] 17. Detener el contenedor de un servicio: aparece en rojo y los demás siguen
- [ ] 18. Detener Redis: lo protegido responde 503 y los catálogos siguen
- [ ] 19. Encender Redis: todo vuelve sin reiniciar servicios
- [ ] 20. En el monolito: todo sigue funcionando contra la misma base
- [ ] 21. Consultar la bitácora: aparecen las operaciones hechas por la API, con usuario e IP
- [ ] 22. Correr las pruebas unitarias, las de contrato y las de integración

Verificaciones extra:
- [x] Un token con `alg: none`, vencido o de otra audiencia es rechazado
- [ ] El rol de base de un servicio no puede escribir en las tablas de otro
- [ ] Misma semilla y misma versión dan el mismo resultado, ahora por la API
- [ ] Ningún `.env`, token ni contraseña está en el repositorio, en las imágenes ni en las
      evidencias

---

## Fuera de alcance en esta etapa

- MongoDB, Google Cloud Storage y nginx: no se vieron en clase
- Motor CUDA o Numba y lotes de 30 o más réplicas
- Límites de consumo (*rate limiting*) y HTTPS con certificados reales
- Las apps de escritorio y móvil: se entregan en el tercer parcial. Los servicios y sus
  contratos quedan listos y documentados para ellas
- Los servicios opcionales del catálogo: `recuperacion`, `dispositivos`, `evidencias`,
  `vacunas` y `configuracion`
