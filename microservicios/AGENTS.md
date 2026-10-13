# AGENTS.md — microservicios

> **Estado: Vigente** · 2026-10-12 · Complementa el `AGENTS.md` de la raíz. Lo marcado como
> **(pendiente)** sigue abierto en el bloque 0 del checklist: pregunta antes de implementarlo.

## Qué hay aquí

Son 26 microservicios Flask pequeños, cada uno con una sola tarea, más una consola web para
probarlos. Los usan **solo** las apps de escritorio (XML) y móvil (JSON). El sistema web (el
monolito) sigue hablando directo con PostgreSQL y no los llama.

- [`docs/arquitectura/microservicios.md`](../docs/arquitectura/microservicios.md) es la
  referencia de cada servicio: su tarea, rutas, las tablas que escribe y lee, a quién llama,
  su puerto y sus llaves de Redis. Si algo de aquí choca con el catálogo, gana el catálogo.
- [`docs/CHECKLIST_SEGUNDO_PARCIAL.md`](../docs/CHECKLIST_SEGUNDO_PARCIAL.md) tiene las
  tareas, quién las tiene y la **definición de terminado** de un servicio.
- `docs/arquitectura/arquitectura_v1.md` describe el sistema final, con MongoDB, Cloud
  Storage y nginx. No lo sigas donde contradiga al catálogo.

```
microservicios/
  comun/        paquete epidemia_comun: lo que todos los servicios repiten
  <servicio>/   uno por servicio del catálogo: app.py, rutas.py, Dockerfile, README.md, tests/
  consola/      página tipo Swagger/Postman para probar los 26
infra/          imagen base de Docker y docker-compose.yml
docs/contratos/ un openapi.json (y su .xsd, si aplica) por servicio
```

## Antes de escribir código

1. Busca el servicio en el catálogo. Si lo que te piden no es la tarea de ese servicio, va
   en otro o es un cambio al catálogo: pregunta, no lo metas donde ya hay un servidor
   levantado.
2. Busca la regla en `backend_web` (`queries.py`, `conversion.py`, `simulaciones.py`,
   `auth.py`) o en `procesamiento/motor`, y úsala. Esas reglas tienen 431 pruebas; una copia
   reescrita en el servicio no tiene ninguna. Si el dominio todavía vive en `queries.py`,
   sácalo a su propio módulo y deja `queries.py` como fachada (LIMP-11e).
3. Si algo hace falta en dos servicios, va en `epidemia_comun`, no copiado.
4. Si `epidemia_comun` todavía no tiene lo que necesitas, agrégalo ahí o avisa a quien
   lleva el bloque A (o el K, si es de Redis). No lo resuelvas dentro del servicio.

## Reglas

1. **Una tarea por servicio.** No agregues rutas de otro dominio a un servicio.
2. **Un dueño por tabla.** Un servicio solo escribe lo que el catálogo dice que escribe;
   todo lo demás lo lee. Su rol de PostgreSQL no tiene permiso para más. Si ves
   `permission denied`, no amplíes el `GRANT`: esa escritura es de otro servicio, y se le
   pide por HTTP.
3. **Bitácora.** Toda escritura se registra con `log_audit(contexto, ..., cur=cur)`, dentro
   de la misma transacción. El `Contexto` sale del token. `audit_log` es de solo inserción.
4. **Formatos.** XML por defecto y JSON con `?format=json` (**pendiente:** aceptar también
   `Accept`).
   - Responde con `responder()` y lee con `leer_cuerpo()`, de la biblioteca. Nunca uses
     `jsonify` ni armes XML a mano.
   - El XML se lee con `defusedxml`.
5. **Datos crudos.** Regresa números, fechas ISO 8601 y claves (`activo`, `critico`,
   `con_casos`). El texto para personas lo arma el cliente, igual que en el monolito
   (LIMP-11a). Los mensajes de validación sí van en español y son los que ya da
   `backend_web`.
6. **Errores.** Siempre RFC 7807 desde la biblioteca, con un `codigo` de su tabla. Un 500
   no expone la traza ni el SQL.
7. **Seguridad.**
   - Toda ruta no pública lleva `@requiere_token(roles=...)`, con los mismos roles que la
     pantalla equivalente del monolito. Las rutas internas llevan `@solo_servicios`.
   - Para llamar a otro servicio por una persona, reenvía su token con `llamar()`. El token
     de servicio es solo para llamadas sin persona detrás (el `simulador`,
     `estado-servicios`).
   - Nunca escribas en un log, en una respuesta ni en la bitácora un token, una contraseña
     o un `password_hash`.
8. **Redis.** Todo pasa por `epidemia_comun` (ver `comun/README.md`); nunca crees un
   `redis.Redis` en un servicio.
   - Sesiones y revocación con `sesiones`, caché con `cache`, candados con `candados` y la
     cola con `cola`. Las demás llaves del catálogo se escriben con `requerido()` u
     `opcional()` de `redis_compartido`.
   - Solo las llaves de `llaves.py`, que son las del catálogo, y siempre con TTL; la cola es
     la única sin él. Una llave nueva va en `llaves.py` y en la tabla del catálogo, y una
     prueba revisa que coincidan.
   - De `sid` y del *refresh* se guarda la huella, no el valor.
   - Con Redis caído, una ruta protegida responde 503 y nunca deja pasar. Los catálogos
     públicos siguen respondiendo.
   - La clave de la caché lleva todo lo que cambia la respuesta, incluido el ámbito de quien
     pregunta. Si no, una persona puede ver datos de otra.
9. **Llamadas entre servicios.**
   - Solo con `llamar()` de la biblioteca, nunca con `requests` directo. Así llevan tiempo
     de espera, token y `X-Correlation-ID`.
   - Un servicio caído se convierte en 503 `SERVICIO_NO_DISPONIBLE`.
   - No reintentes escrituras a ciegas.
   - Cada llamada nueva se anota en la columna "Llama a" del catálogo.
10. **Puertos.** El servicio escucha en 8000 dentro del contenedor y publica el puerto del
    catálogo. Un puerto no se cambia sin cambiar el catálogo.
11. **Contratos.** Una ruta nueva o un cambio de forma se refleja en
    `docs/contratos/<servicio>/` en el mismo PR. Un cambio incompatible va a `/api/v2/`.
12. **Dependencias.** Nada de MongoDB, Cloud Storage ni nginx. Una dependencia nueva se
    acuerda con el equipo y va en los requerimientos de `comun`, no de un solo servicio.
13. **Python.** Compatible con 3.9 (regla 11 de la raíz), aunque la imagen use una versión
    más nueva: el código de `backend_web` también lo corre el monolito.
14. **El monolito no se toca para consumir servicios.** Si una tarea pide que la web llame a
    un microservicio, pregunta: va contra lo decidido.

## Agregar o cambiar un servicio

1. Primero el catálogo: la fila completa, con tarea, rutas, tablas, llamadas y puerto.
2. `python scripts/nuevo_servicio.py <nombre> <puerto>` genera la carpeta, el `Dockerfile`,
   la entrada en el compose, el contrato vacío y una prueba de `/health`.
3. La migración de su rol de PostgreSQL. Confirma el número antes de crearla (regla 6 de la
   raíz).
4. Rutas, contrato, pruebas y README hasta cumplir la definición de terminado del checklist.

## Pruebas

- **Unitarias:** con la base y Redis simulados. No necesitan Docker.
- **Integración:** contra los contenedores, con la base `simulador_epidemico_pruebas` y un
  Redis aparte. **Nunca** contra la base de la demostración.
- **Contrato:** cada ejemplo XML valida contra su XSD, y el `openapi.json` del servicio es
  igual al de `docs/contratos/`.
- Antes de dar algo por terminado, las 431 pruebas del monolito también tienen que pasar.

## Comandos

Ya existen:

- Pruebas de la biblioteca:
  `python -m pytest microservicios/comun/tests`
- Solo Redis (necesita `infra/.env`, copiado de `infra/.env.example`):
  `docker compose -f infra/docker-compose.yml up -d redis`

Existirán cuando estén los bloques A y J:

- Levantar todo: `docker compose -f infra/docker-compose.yml up --build`
- Solo un dominio: `docker compose -f infra/docker-compose.yml --profile escenarios up`
- Un servicio: `docker compose -f infra/docker-compose.yml up --build <servicio>`
- Salud: `curl "http://localhost:<puerto>/health?format=json"`
- Swagger: `http://localhost:<puerto>/docs` · Consola: `http://localhost:5260`

## Decisiones pendientes: pregunta antes de implementar

- Si se acepta `Accept: application/json` además de `?format=json`.
- Rutas en inglés, como en el catálogo, o en español.
- Si las apps de escritorio y móvil se entregan en este parcial o solo sus servicios.
- Si hace falta la `pasarela` o las apps usan el directorio de `estado-servicios`.
- `pytest` o `unittest`, y `xmlschema` o `lxml` para los XSD.

Cuando se decidan, quedarán en `docs/decisiones.md`, y esta sección se actualiza.

## Qué manda dentro de `microservicios/`

1. Lo que pida la persona en la sesión.
2. `docs/decisiones.md`.
3. El catálogo (`docs/arquitectura/microservicios.md`).
4. Este archivo.
5. El `AGENTS.md` de la raíz.
6. `docs/arquitectura/arquitectura_v1.md`.

Para el esquema de la base, las migraciones ganan sobre cualquier documento.
