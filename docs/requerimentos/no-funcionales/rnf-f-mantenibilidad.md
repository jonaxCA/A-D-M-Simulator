> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-F: Mantenibilidad

Cómo se trabaja el código para que seis personas lo puedan revisar y cambiar. Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-F01 | Todo el código está en Git, con el flujo de ramas de `CONTRIBUTING.md` | Una rama por tarea, commits chicos y nadie aprueba su propio PR | Infraestructura | Hecho |
| RNF-F03 | Cada servicio documenta su API con OpenAPI | `/docs` y `/openapi.json` en cada servicio; los contratos están en [`docs/contratos/`](../../contratos/) | Microservicios | Hecho |
| RNF-F04 | El código tiene pruebas con pytest (D14) | `python -m pytest microservicios`, `python -m pytest frontend_desktop` y `python -m pytest procesamiento/tests` pasan. Corren contra la base de pruebas, nunca contra la de la demostración | Microservicios, Escritorio | Hecho |
| RNF-F05 | Hay pruebas de los flujos completos entre servicios | `python infra/pruebas_integracion.py` corre un flujo de punta a punta | Microservicios | Hecho |
| RNF-F06 | Los contratos se prueban | Las respuestas con XSD se validan contra él, y el contrato del motor tiene su prueba (`test_contrato_motor.py`) | Microservicios | Hecho |
| RNF-F08 | Cada servicio corre en su propio contenedor | Un Dockerfile y un contenedor por microservicio | Infraestructura | Hecho |
| RNF-F10 | La configuración va en variables de entorno | `infra/genera_env.py` crea `infra/.env`; nada que cambie entre máquinas está en el código | Infraestructura | Hecho |
| RNF-F11 | El esquema de la base son migraciones SQL numeradas (D7, D17) | Una migración aplicada no se edita: se agrega otra. `python datos/scripts/verifica_migraciones.py` no muestra diferencias | Bases de datos | Hecho |
| RNF-F15 | Cada servicio se despliega y se actualiza sin tocar a los demás | Reconstruir un contenedor no reinicia a los otros | Microservicios, Infraestructura | Hecho |
| RNF-F19 | El código es chico y legible | Sigue el estilo de `AGENTS.md`: sin clases que no guarden estado, sin validación de más y con la biblioteca estándar de preferencia | Microservicios | Hecho |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-F02 | Estructura estándar por capa | La estructura es la del repositorio; no hay más que comprobar |
| RNF-F07 | Integración continua con GitHub Actions | No la pide la rúbrica (arquitectura v3, §10) |
| RNF-F09 | Un `docker-compose.yml` levanta todo | Pasa a RNF-H05 |
| RNF-F12 | Logs en JSON con correlación | Pasa a RNF-J01 y RNF-J06 |
| RNF-F13 | Código autodocumentado | Se cubre con RNF-F19 |
| RNF-F14 | Sin dependencias circulares | El catálogo ya dice a quién llama cada servicio |
| RNF-F16 | Parámetros operativos fuera del código | Se cubre con RNF-F10 |
| RNF-F17 | Suite de regresión | Se cubre con RNF-F04 |
| RNF-F18 | Linter para Python, Kotlin y C++ | No hay integración continua; el motor ya no es de C++ (RNF-L16) |
