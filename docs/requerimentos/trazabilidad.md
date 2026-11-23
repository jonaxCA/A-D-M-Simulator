> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# Matriz de trazabilidad

Cada renglón une un paso de [`procesos_v3.md`](../arquitectura/procesos_v3.md) con sus requerimientos, su componente, su servicio y su prueba. Los rangos (RF-F04 a RF-F08) saltan los ID retirados.

La columna **Prueba** dice dónde están las pruebas que tocan ese paso, no que cada requerimiento tenga la suya: eso se revisa al escribir el plan de implementación. Las pruebas de la móvil están en `frontend_movil/app/src/test/`.

## Por paso de proceso

| Paso | RF | RNF | Componente | Servicio | Prueba |
|---|---|---|---|---|---|
| 1.1 | RF-A01, RF-A02, RF-A08, RF-A14, RF-I01, RF-I13 | RNF-D11, RNF-D12, RNF-G02 | Móvil, Microservicios, Seguridad | `estado-servicios`, `auth`, `sesiones` | `microservicios/auth/tests`, `microservicios/sesiones/tests`; móvil: `sesion/`, `red/` |
| 1.2 | RF-A09, RF-I14, RF-I16 | RNF-D14 | Móvil, Microservicios | `dispositivos` | `microservicios/dispositivos/tests` |
| 1.3 | RF-B01, RF-B02, RF-I17 | RNF-G02 | Móvil, Microservicios | `enfermedades`, `regiones` | `microservicios/enfermedades/tests`, `microservicios/regiones/tests` |
| 1.4 | RF-C01, RF-C02, RF-C06, RF-C07, RF-I03, RF-I04, RF-I07 | RNF-D15 | Móvil | — (local) | Móvil: `local/`, `ui/` |
| 1.5 | RF-C03, RF-I05 | RNF-D23 | Móvil | — (local) | Móvil: `local/` |
| 1.6 | RF-C08, RF-C09, RF-C10, RF-C12, RF-C14, RF-C19, RF-C21, RF-I08, RF-I10 | RNF-A05, RNF-A08, RNF-C13, RNF-K08 | Móvil, Microservicios | `sincronizacion`, `casos`, `notificaciones` | `microservicios/sincronizacion/tests`, `microservicios/casos/tests`; móvil: `trabajos/` |
| 1.7 | RF-C03 | RNF-C09, RNF-C19, RNF-D24, RNF-D27, RNF-K12 | Móvil, Microservicios | `evidencias` | `microservicios/evidencias/tests` |
| 1.8 | RF-C04, RF-C05, RF-C13, RF-I06 | RNF-L19 | Móvil, Microservicios | `vacunas` | `microservicios/vacunas/tests` |
| 1.9 | RF-G01, RF-G02, RF-G03, RF-G11, RF-C20 | RNF-A07, RNF-D17, RNF-L12 | Web | — (directo a PostgreSQL, D20) | `backend_web/tests` |
| 2.1 | RF-A01, RF-A02, RF-A08, RF-A14, RF-H01, RF-H17 | RNF-D11, RNF-D12, RNF-G03 | Escritorio, Microservicios, Seguridad | `estado-servicios`, `auth`, `sesiones`, `usuarios` | `frontend_desktop/tests/test_api.py` |
| 2.2 | RF-H02, RF-B01, RF-B02, RF-B03 | RNF-G03 | Escritorio, Microservicios | `escenarios`, `enfermedades`, `regiones`, `tipos-intervencion` | `microservicios/escenarios/tests`, `frontend_desktop/tests/test_servicios.py` |
| 2.3 | RF-D01, RF-D04, RF-D08 | RNF-K02 | Escritorio, Microservicios | `escenarios` | `microservicios/escenarios/tests` |
| 2.4 | RF-D02, RF-H03, RF-H04 | RNF-G06 | Escritorio, Microservicios | `intervenciones` | `microservicios/intervenciones/tests` |
| 2.5 | RF-D03, RF-B10 | RNF-D04 | Escritorio, Microservicios | `validacion` | `microservicios/validacion/tests` |
| 2.6 | RF-D06, RF-D07, RF-H05 | RNF-G06, RNF-D04 | Escritorio, Microservicios | `escenarios-xml` | `microservicios/escenarios_xml/tests`, `frontend_desktop/tests/test_xmlio.py`, `test_esquemas.py` |
| 2.7 | RF-D15, RF-D13 | RNF-D14 | Escritorio, Microservicios | `aprobacion`, `notificaciones` | `microservicios/aprobacion/tests` |
| 2.8 | RF-D16, RF-D13 | RNF-D14 | Web, Microservicios | — (directo a PostgreSQL, D4 y D20); `aprobacion` para un cliente | `backend_web/tests/test_escenarios.py`, `microservicios/aprobacion/tests` |
| 2.9 | RF-D17, RF-H15 | RNF-G03 | Escritorio, Microservicios | `notificaciones`, `escenarios` | `microservicios/notificaciones/tests` |
| 3.1 | RF-E01, RF-E02, RF-E03, RF-E04, RF-E09, RF-E15, RF-E21, RF-H07, RF-H20 | RNF-A14, RNF-B04 | Escritorio, Microservicios | `corridas` | `microservicios/corridas/tests`, `backend_web/tests/test_corridas_servicio.py` |
| 3.2 | RF-E05, RF-E11, RF-E12, RF-E19, RF-E20 | RNF-A02, RNF-A04, RNF-A13, RNF-C03, RNF-C08, RNF-G09, RNF-J12, RNF-K03 | Microservicios, Bases de datos | `simulador`, `notificaciones` | `microservicios/simulador/tests`, `procesamiento/tests`, `backend_web/tests/test_corridas_interrumpidas.py` |
| 3.3 | RF-E05, RF-E06, RF-H08 | RNF-G03 | Escritorio, Microservicios | `corridas` | `microservicios/corridas/tests` |
| 3.4 | RF-E11, RF-H15 | RNF-G03 | Escritorio, Microservicios | `notificaciones` | `microservicios/notificaciones/tests` |
| 3.5 | RF-F01, RF-F02, RF-F04 a RF-F08, RF-F19, RF-F20, RF-F22, RF-F23, RF-H10, RF-H11, RF-H21, RF-H22 | RNF-A09, RNF-I10, RNF-I11, RNF-I16 | Escritorio, Microservicios | `comparacion`, `resultados`, `pareto` | `microservicios/comparacion/tests`, `microservicios/pareto/tests`, `microservicios/resultados/tests`, `frontend_desktop/tests/test_resumen.py`, `procesamiento/tests/test_pareto.py` |
| 3.6 | RF-F09, RF-F11, RF-F17, RF-H13 | RNF-D17, RNF-K12 | Escritorio, Microservicios | `evidencias` (`POST /api/v1/reports`, D2); falta que el escritorio lo suba | `microservicios/evidencias/tests` |
| 3.7 | RF-F21, RF-F01, RF-F04, RF-F19, RF-G02, RF-G09 | RNF-A09, RNF-L12 | Web, Microservicios | — (directo a PostgreSQL); con D28, `resultados` para las curvas | `backend_web/tests`, `microservicios/resultados/tests` |

## Funciones de soporte

| Función | RF | RNF | Componente | Servicio | Prueba |
|---|---|---|---|---|---|
| Sesión de la web | RF-A11, RF-A12 | RNF-D06, RNF-D07, RNF-D21 | Web, Seguridad | — | `backend_web/tests` |
| Roles, permisos y auditoría | RF-A04, RF-A05, RF-A06, RF-A13 | RNF-D13, RNF-D14, RNF-D25 | Seguridad, Bases de datos | `usuarios`, `roles` | `microservicios/usuarios/tests`, `microservicios/roles/tests`, `backend_web/tests/test_auditoria.py`, `test_bitacora.py` |
| Catálogos | RF-B01 a RF-B03, RF-B09 a RF-B17 | RNF-I09 | Web, Microservicios | `enfermedades`, `parametros`, `regiones`, `poblacion`, `tipos-intervencion` | Las pruebas de cada servicio |
| Tablero y monitoreo epidemiológico | RF-G04 a RF-G06, RF-G12, RF-G15, RF-G16 | RNF-A06, RNF-E03 | Web | — (`indicadores`, `series` y `zonas` existen, pero la web no los llama) | `backend_web/tests/test_monitoreo.py` |
| App de escritorio, lo demás | RF-H14, RF-H18, RF-H19, RF-H23, RF-H24 | RNF-E01, RNF-E06 | Escritorio | `estado-servicios`, `sesiones` | `frontend_desktop/tests/test_humo.py` |
| App Android, lo demás | RF-I02, RF-I09, RF-I15, RF-I18 a RF-I22 | RNF-E01, RNF-E11 | Móvil | `usuarios`, `notificaciones` | Móvil: `avisos/`, `ui/` |
| Sitio público | RF-J01, RF-J03 | RNF-D15 | Web | — | `backend_web/tests` |
| Monitoreo del sistema | RF-K01 a RF-K05, RF-K08, RF-K10 a RF-K12 | RNF-J01, RNF-J05, RNF-J06, RNF-J13, RNF-C16 | Monitoreo | `estado-servicios`, `/health` de cada servicio | `microservicios/estado_servicios/tests`, `microservicios/comun/tests` |
| Administración | RF-L01 a RF-L05 | RNF-D20 | Web, Microservicios | `usuarios`, `roles`, `sesiones`, `dispositivos` | `microservicios/usuarios/tests`, `microservicios/dispositivos/tests` |
| Seguridad de la plataforma | — | RNF-D01, RNF-D03, RNF-D08 a RNF-D10, RNF-D26, RNF-D28 | Seguridad, Infraestructura | `epidemia_comun`, nginx | `microservicios/comun/tests`; nginx: falta |
| Despliegue y datos | — | RNF-H01 a RNF-H18, RNF-K01 a RNF-K18, RNF-A16, RNF-A17 | Infraestructura, Bases de datos | — | `infra/pruebas_integracion.py`, `datos/scripts/verifica_migraciones.py`; Locust: falta |

## Por rol

| Rol | Dónde participa | Requerimientos principales |
|---|---|---|
| CAPTURISTA | Pasos 1.1 a 1.8 | RF-A01, RF-A09, RF-C01 a RF-C14, RF-C21, RF-I01 a RF-I22 |
| EPIDEMIOLOGO | Pasos 1.9, 2.8 y 3.7 | RF-B01, RF-B09, RF-B11, RF-C19, RF-C20, RF-D16, RF-D18, RF-F21, RF-G01 a RF-G15 |
| ANALISTA | Pasos 2.1 a 2.7, 2.9 y 3.1 a 3.7 | RF-D01 a RF-D20, RF-E01 a RF-E21, RF-F01 a RF-F23, RF-H01 a RF-H24 |
| ADMINISTRADOR | Soporte; también entra al escritorio | RF-A04 a RF-A06, RF-B02, RF-L01 a RF-L05, RF-K01 a RF-K12 |
| Visitante sin sesión | Soporte | RF-J01, RF-J03 |

## Requerimientos que faltan, por brecha

Los que no están en «Hecho», agrupados por la brecha de [`brechas_v3.md`](../arquitectura/brechas_v3.md) que los cierra:

| Brecha | Requerimientos |
|---|---|
| I1 (notificaciones) | RF-C19, RF-D15, RF-D16 |
| I3 (Redis en la web) | RF-A12 |
| D-1 (MongoDB) | RF-E20, RF-F21, RF-F22, RF-K03, RNF-C08, RNF-K03, RNF-K14, RNF-K17, RNF-L07 |
| D-3 (Cloud Storage y URLs firmadas) | RF-C03, RF-C20, RF-F17, RNF-B01, RNF-C09, RNF-C19, RNF-D17, RNF-D27, RNF-K12, RNF-K18 |
| D-5 (carga de archivos en la web) | RF-G16 |
| D-6 (volumen) | RNF-A09, RNF-A17 |
| S2 (límites de consumo) | RNF-D08 |
| S5 (secretos en GCP) | RNF-D03 |
| S6 (nginx y HTTPS) | RF-K11, RNF-C10, RNF-D01, RNF-D09, RNF-H16, RNF-L11 |
| N1, N2 (despliegue) | RNF-B09, RNF-D10, RNF-H02, RNF-H07, RNF-H17, RNF-H18, RNF-L09 |
| N3, N4 (salud y panel) | RF-K05, RF-K10, RF-K12, RNF-J05 |
| N5 (fallos) | RNF-C02, RNF-C16, RNF-C18 |
| N6 (logs) | RF-K08, RNF-J13 |
| A3 (bandas encimadas) | RF-F23, RF-H22 |
| A4, A5 (Locust) | RNF-A01, RNF-A05 a RNF-A08, RNF-A14, RNF-A16, RNF-L14 |
| C3, C8 (móvil) | RF-I19, RF-I20, RNF-E11 |
| C10 (JWT en el escritorio) | RF-H23 |
| D1 (permisos) | RF-A05, RF-G11, RF-L05 |
| D8, D19 (corridas) | RF-E03, RF-E19, RNF-C03 |
| Escritorio (bloque A) | RF-E15, RF-F20, RF-H20, RF-H21 |
| Sin brecha registrada | RNF-D07, RNF-D21, RNF-E08 |
| Por verificar | RF-F02, RF-H24, RF-I22, RNF-D05, RNF-D06, RNF-E03, RNF-E06 |
