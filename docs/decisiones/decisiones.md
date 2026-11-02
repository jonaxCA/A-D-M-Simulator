# Registro de decisiones

Una decisión por archivo, con la estructura de [`plantilla_ADR.md`](plantilla_ADR.md). El número es el de siempre (D1, D2…) para que no se rompan las referencias en otros documentos.

Estados: **Aceptada**, **Pendiente** (nadie ha decidido), **Propuesta** (hay una opción recomendada sin confirmar), **Por confirmar** (ya está en uso o se asumió, falta que el equipo la confirme) y **Reemplazada por DXX**.

| #   | Decisión                                                                       | Estado        | Depende de  | Archivo                                                                                |
| --- | ---                                                                            | ---           | ---         | ---                                                                                    |
| D1  | Quién captura casos, aprueba versiones y consulta la auditoría                 | Pendiente     | —           | [D01-permisos-y-auditoria.md](D01-permisos-y-auditoria.md)                             |
| D2  | Papel del SEIR frente al modelo basado en agentes                              | Pendiente     | D22         | [D02-papel-del-seir.md](D02-papel-del-seir.md)                                         |
| D3  | Unidad de costo: personas-día, pesos o ambos por separado                      | Pendiente     | —           | [D03-unidad-de-costo.md](D03-unidad-de-costo.md)                                       |
| D4  | Reparto del trabajo con escenarios entre la web y la app de escritorio         | Pendiente     | D1          | [D04-web-contra-escritorio.md](D04-web-contra-escritorio.md)                           |
| D5  | Una versión es una fotografía: congela población y parámetros                  | Aceptada      | —           | [D05-foto-de-la-version.md](D05-foto-de-la-version.md)                                 |
| D6  | Qué significa la población de un escenario                                     | Pendiente     | D22         | [D06-poblacion-del-escenario.md](D06-poblacion-del-escenario.md)                       |
| D7  | Política de migraciones: datos contra esquema                                  | Pendiente     | —           | [D07-politica-de-migraciones.md](D07-politica-de-migraciones.md)                       |
| D8  | Cuántas réplicas usa una comparación y cómo se resumen                         | Pendiente     | D22         | [D08-replicas-de-una-comparacion.md](D08-replicas-de-una-comparacion.md)               |
| D9  | XML por defecto y JSON por parámetro o cabecera                                | Aceptada      | —           | [D09-formato-xml-por-defecto.md](D09-formato-xml-por-defecto.md)                       |
| D10 | Microservicios en el segundo parcial; apps de escritorio y móvil en el tercero | Aceptada      | —           | [D10-entregas-por-parcial.md](D10-entregas-por-parcial.md)                             |
| D11 | Rutas de las API en inglés                                                     | Aceptada      | —           | [D11-rutas-en-ingles.md](D11-rutas-en-ingles.md)                                       |
| D12 | Nombres de los servicios en español                                            | Aceptada      | —           | [D12-servicios-en-espanol.md](D12-servicios-en-espanol.md)                             |
| D13 | Sin pasarela: las apps usan el directorio de `estado-servicios`                | Aceptada      | —           | [D13-sin-pasarela.md](D13-sin-pasarela.md)                                             |
| D14 | Pruebas con `pytest`                                                           | Aceptada      | —           | [D14-pruebas-con-pytest.md](D14-pruebas-con-pytest.md)                                 |
| D15 | XSD validado con `xmlschema`; XML leído con `defusedxml`                       | Aceptada      | —           | [D15-xsd-con-xmlschema.md](D15-xsd-con-xmlschema.md)                                   |
| D16 | Migraciones del segundo parcial reservadas: 026 en adelante                    | Aceptada      | D7          | [D16-migraciones-desde-la-026.md](D16-migraciones-desde-la-026.md)                     |
| D17 | Migraciones SQL numeradas en lugar de Alembic                                  | Por confirmar | —           | [D17-migraciones-sql-numeradas.md](D17-migraciones-sql-numeradas.md)                   |
| D18 | Una sola instancia de PostgreSQL con un rol por servicio                       | Por confirmar | —           | [D18-un-postgres-un-rol-por-servicio.md](D18-un-postgres-un-rol-por-servicio.md)       |
| D19 | Redis sin datos autoritativos                                                  | Por confirmar | —           | [D19-redis-sin-datos-autoritativos.md](D19-redis-sin-datos-autoritativos.md)           |
| D20 | Migración gradual del monolito con fachada en la web                           | Por confirmar | —           | [D20-migracion-gradual-con-fachada.md](D20-migracion-gradual-con-fachada.md)           |
| D21 | Lo no implementado pasa al tercer parcial                                      | Aceptada      | —           | [D21-pendientes-pasan-al-tercer-parcial.md](D21-pendientes-pasan-al-tercer-parcial.md) |
| D22 | Implementar el modelo basado en agentes (ABM)                                  | Aceptada      | D2          | [D22-modelo-basado-en-agentes.md](D22-modelo-basado-en-agentes.md)                     |
| D23 | Tecnología del ABM: CPU o GPU                                                  | Pendiente     | D22         | [D23-tecnologia-del-abm.md](D23-tecnologia-del-abm.md)                                 |
| D24 | Calibración y parámetros de los agentes                                        | Pendiente     | D22         | [D24-calibracion-del-abm.md](D24-calibracion-del-abm.md)                               |
| D25 | nginx como terminador TLS y entrada única                                      | Propuesta     | D13         | [D25-nginx-como-entrada.md](D25-nginx-como-entrada.md)                                 |
| D26 | Certificado HTTPS                                                              | Pendiente     | D25         | [D26-certificado-https.md](D26-certificado-https.md)                                   |
| D27 | Servicios nuevos para la app móvil                                             | Pendiente     | —           | [D27-servicios-nuevos-para-la-movil.md](D27-servicios-nuevos-para-la-movil.md)         |
| D28 | Qué datos van a MongoDB                                                        | Pendiente     | D21         | [D28-uso-de-mongodb.md](D28-uso-de-mongodb.md)                                         |
| D29 | Volumen de datos de alto volumen                                               | Pendiente     | D6, D8, D28 | [D29-volumen-de-datos.md](D29-volumen-de-datos.md)                                     |
