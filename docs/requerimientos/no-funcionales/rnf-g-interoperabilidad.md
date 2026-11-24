> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-G: Interoperabilidad

Cómo hablan los clientes con los servicios. Las convenciones están en [`microservicios.md`](../../arquitectura/microservicios.md). Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-G01 | Todas las rutas de los servicios van bajo `/api/v1/`, en inglés (D11) | Ninguna ruta de un servicio queda fuera del prefijo, salvo `/health` y `/docs` | Microservicios | Hecho |
| RNF-G02 | La app Android consume solo JSON | Todas sus peticiones piden JSON | Móvil | Hecho |
| RNF-G03 | La app de escritorio consume solo XML | Todas sus peticiones piden XML | Escritorio | Hecho |
| RNF-G04 | Cada servicio responde en XML o en JSON, según se le pida (D9) | XML por omisión; JSON con `?format=json` o con `Accept: application/json`. Un formato desconocido responde 400 | Microservicios | Hecho |
| RNF-G06 | El XML de un escenario tiene su esquema | [`escenario.xsd`](../../contratos/escenarios-xml/escenario.xsd), validado con `xmlschema` (D15) en la app y en el servidor | Microservicios, Escritorio | Hecho |
| RNF-G07 | El motor tiene un contrato de entrada y de salida | [`docs/contratos/motor/`](../../contratos/motor/), con su versión en código en `procesamiento/contrato.py` | Microservicios | Hecho |
| RNF-G08 | Los formatos de intercambio son tres | XML para escenarios, CSV y PDF para lo que se exporta, y JSON o XML en la API | Microservicios, Escritorio, Web | Hecho |
| RNF-G09 | Los tres motores cumplen el mismo contrato | `seir-ref`, `abm-ref` y `abm-gpu` pasan las mismas pruebas de conformidad | Microservicios | Hecho |
| RNF-G15 | Todos los servicios responden los errores igual | RFC 7807 con un `codigo` estable | Microservicios | Hecho |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-G05 | OpenAPI | Pasa a RNF-F03 |
| RNF-G10 | HTTPS y WebSocket | HTTPS pasa a RNF-D01; no hay WebSocket |
| RNF-G11 | Fechas en ISO 8601 | No se comprobó en todos los servicios; lo fija cada contrato |
| RNF-G12 | UTF-8 | Es lo que ya hacen Flask y PostgreSQL; no hay más que comprobar |
| RNF-G13 | UUID v4 para todo recurso | Los identificadores son números de la base; solo el caso lleva un `local_uuid` |
| RNF-G14 | Paginación con cursor | `GET /runs` regresa como mucho 100 corridas, sin paginar (RNF-B04) |
