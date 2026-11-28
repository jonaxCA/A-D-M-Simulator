# Documentación de EPIDEMIA

Aquí está todo lo que se escribe sobre el proyecto y no es código: cómo está armado, por qué se
decidió así, qué hace cada servicio, qué se pidió y cómo se probó. Si llegas nuevo, empieza por
la instalación y por el catálogo de microservicios; lo demás lo vas abriendo según lo necesites.

## Qué hay

| Carpeta o archivo   | Qué hay                                                                                              |
|---------------------|------------------------------------------------------------------------------------------------------|
| `arquitectura/`     | La arquitectura (la v3 es la del tercer parcial), el catálogo de microservicios y el modelo de datos |
| `contratos/`        | El contrato de cada servicio (OpenAPI, XSD y ejemplos) y la colección de Postman                     |
| `decisiones/`       | Las decisiones del equipo (D1 en adelante), su plantilla y las que siguen abiertas                   |
| `requerimientos/`    | Requerimientos, historias de usuario, reglas de negocio, permisos por rol y trazabilidad             |
| `manuales/`         | Manual de usuario de las apps de escritorio, web y móvil                                             |
| `pruebas/`          | Resultados de las pruebas (carga, volumen, fallos, calibración) y cómo repetirlas                    |
| `parciales/`        | El plan y el checklist de cada parcial                                                               |
| `desarrollo/`       | Guías para quien programa (todavía por escribir)                                                     |
| `rubrica/`          | Los textos de la materia; no se editan                                                               |
| `INSTALACION.md`    | Instalación a mano, base de pruebas y problemas frecuentes                                           |
| `DESPLIEGUE_GCP.md` | Cómo se despliega en la nube                                                                         |
| `todo.md`           | Pendientes de la documentación                                                                       |

## Antes de fiarte de un documento

- Si en su encabezado dice **Obsoleto**, no lo tomes como fuente.
- Si contradice a `decisiones/decisiones.md`, ganan las decisiones.
- Para el esquema de la base mandan las migraciones de `datos/postgres/migraciones/`, no estos
  documentos.
- Si el catálogo de microservicios y el código no coinciden, manda el código.

## Si vas a escribir aquí

Que sea en español, con cambios pequeños y sin repetir lo que ya está en otra carpeta: mejor un
enlace. Si agregas o quitas una carpeta, actualiza la tabla de arriba y el índice de
[AGENTS.md](AGENTS.md), y revisa que los enlaces sigan funcionando.

## Dónde seguir leyendo

- Cómo levantar todo: [INSTALACION.md](INSTALACION.md).
- Qué hace cada servicio: [arquitectura/microservicios.md](arquitectura/microservicios.md).
- Por qué se hizo así: [decisiones/decisiones.md](decisiones/decisiones.md).
- Qué se pidió: [requerimientos/README.md](requerimientos/README.md).
- Cómo colaborar: [CONTRIBUTING.md](../CONTRIBUTING.md).
