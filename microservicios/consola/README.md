# EPIDEMIA - Consola de pruebas

La página para comprobar que los 26 servicios funcionan, tipo Swagger y Postman. Hace las
veces de las apps de escritorio y móvil mientras no existen. No es uno de los 26: no tiene
base, Redis ni contrato, y `estado-servicios` no la sondea.

Puerto externo: 5260; puerto interno en Docker: 8000. Ábrela en `http://localhost:5260`,
con `localhost` y no con `127.0.0.1`: cada servicio abre CORS solo para `CONSOLE_ORIGIN`
(por omisión, `http://localhost:5260`), y con otro origen el navegador bloquea las llamadas.

## Cómo funciona

El servidor (`app.py`) solo entrega la página. Todo lo demás pasa en el navegador:

1. Pide el directorio a `estado-servicios` (`GET /api/v1/services`), en la URL del campo
   **Directorio** (por omisión, la de `URL_DIRECTORIO`).
2. Llama a cada servicio directo, con la URL que da el directorio. No hay pasarela (D13).

| Pestaña  | Qué hace |
|----------|----------|
| Salud    | Los 26 con su estado, causa, versión, latencia y la hora del sondeo, leídos de `GET /api/v1/services/health`. Se actualiza cada 10 s; un servicio caído sale en rojo |
| Swagger  | El contrato del servicio elegido en Swagger UI. "Try it out" va a la URL del directorio y lleva el token de la sesión |
| Probador | Servicio, operación, parámetros de ruta y de consulta, y cuerpo en JSON o XML (con el ejemplo del contrato). Muestra el código, el tiempo, las cabeceras (con el `X-Correlation-ID`) y el cuerpo con formato. **Copiar como curl** arma el comando de la petición |
| Recorrido | Los 22 pasos del guion de aceptación, en orden, con lo que pide y responde cada uno y los ids que guarda para los siguientes. **Descargar resumen** baja un JSON para `evidencias/` |

**Sesión:** el captcha y el inicio de sesión los pide a `auth`, renovar a `sesiones`
(`/refresh`) y cerrar también a `sesiones` (`/logout`). El *access* y el *refresh* viven
solo en la memoria de la página: nunca se guardan en el navegador, así que recargarla cierra
la sesión de la consola.

**Lo que nunca muestra:**
- contraseñas: el campo se vacía al enviarlo, y en cualquier cuerpo una clave `password`
  sale como `••••••`;
- tokens completos: `access_token`, `refresh_token` y `token` salen recortados, en el
  probador y en las respuestas de Swagger;
- en el `curl`, el token va como `$TOKEN` y la contraseña como `<contraseña>`;
- Swagger UI arma su propio `curl` con el token completo, así que ese bloque se oculta.

Las respuestas se pintan siempre como texto, nunca como HTML. La página trae una política de
contenido (CSP): solo carga sus scripts y los de Swagger UI (unpkg.com, versión fija), y el
formulario no puede mandar la contraseña en la URL aunque falle el JavaScript. Swagger UI se
descarga de internet la primera vez que se abre su pestaña.

## Variables

| Variable         | Por defecto             | Qué es |
|------------------|-------------------------|--------|
| `URL_DIRECTORIO` | `http://localhost:5262` | `estado-servicios` visto desde el navegador; se puede cambiar en la página |

En cada servicio, `CONSOLE_ORIGIN` es el origen de la consola. El compose lo pone en los 26.

## Probarlo

```bash
python -m pytest microservicios/consola
docker compose -f infra/docker-compose.yml --profile '*' up -d --build --wait
```

Fuera de Docker: `python -m microservicios.consola.app` (en `127.0.0.1:5260`), y cada servicio
necesita `CONSOLE_ORIGIN=http://localhost:5260` en su entorno.

## Recorrido de aceptación

Los pasos están en `estatico/recorrido.js`, uno por paso del guion del checklist (con `a` y
`b` donde uno necesita otra sesión o un dato más). **Seguir** corre en orden los automáticos y
se detiene en los que completa la persona:

- **Iniciar sesión** (5, 7a y 12a): analista, administrador y epidemióloga. La persona
  escribe la contraseña y la respuesta del captcha; el recorrido no lo resuelve solo, y la
  contraseña no se guarda. Los casos del paso 7 los captura el administrador, porque la
  demostración no tiene cuenta de CAPTURISTA.
- **El costo de las intervenciones** (8b): pareto no traza la frontera sin costos (regla 8), y
  en la demostración ningún tipo de intervención lo tiene. La persona escribe el importe de
  VACUNACION y de CIERRE_ESCUELAS, y el administrador lo guarda con la marca de supuesto y la
  fuente "Supuesto del recorrido de aceptación". El costo vive en el tipo: cambia el de todos
  los escenarios de esa base.
- **Lo que pasa fuera de la consola** (1, 4, 17 a 22): levantar el compose, detener un
  servicio o Redis, el monolito y las pruebas. Los pasos 17 a 19 tienen **Comprobar**, que
  revisa el resultado por la API.

Cada paso anota sus peticiones (con la respuesta, sin secretos) y lo que comprobó. Las sesiones
del recorrido son aparte de la de arriba y también viven solo en la memoria de la página. El
resumen descargable lleva cada petición (método, ruta, código, tiempo y `X-Correlation-ID`) y
los ids guardados, sin cuerpos de respuesta ni tokens.

Los pasos 15 y 16 cierran las sesiones de la analista y de la epidemióloga: para volver a
correrlos, **Empezar de nuevo**.
