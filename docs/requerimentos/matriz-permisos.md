> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# Matriz de permisos

Qué puede hacer cada rol, según [D1](../decisiones/D01-permisos-y-auditoria.md) y [D4](../decisiones/D04-web-contra-escritorio.md). Los permisos viven en `role_permissions` (migración 010); cada ruta lleva su candado (RF-A05).

- ✓ puede hacerlo.
- — no puede; la ruta le responde 403.
- ? sin decidir.

| Operación | Dónde | ADMINISTRADOR | EPIDEMIOLOGO | ANALISTA | CAPTURISTA |
|---|---|---|---|---|---|
| Iniciar y cerrar sesión | Todas | ✓ | ✓ | ✓ | ✓ |
| Ver el sitio público | Web | ✓ | ✓ | ✓ | ✓ |
| Ver su perfil y sus avisos | Android, escritorio | ✓ | ✓ | ✓ | ✓ |
| Ver el tablero y el mapa | Web | ✓ | ✓ | ✓ | ✓ |
| Ver el monitoreo epidemiológico y exportar CSV | Web | ✓ | ✓ | ✓ | — |
| Consultar catálogos | Todas | ✓ | ✓ | ✓ | ✓ |
| Dar de alta, editar o dar de baja enfermedades | Web | ✓ | ✓ | — | — |
| Corregir población y bandas de edad | Web | ✓ | — | — | — |
| Fijar el costo unitario de una intervención | Web | ✓ | ✓ | — | — |
| Registrar casos y fotos | Android | — | — | — | ✓ |
| Corregir un caso (D47) | Android, web | — | ✓ | — | ✓ (los suyos, pendientes) |
| Validar, descartar o marcar duplicado un caso (D47) | Web, escritorio | — | ✓ | — | — |
| Registrar lotes de vacuna y aplicar dosis | Android | ? | — | — | ✓ |
| Consultar escenarios y versiones | Web | ✓ | ✓ | ✓ | — |
| Crear y editar escenarios e intervenciones | Escritorio | ✓ | — | ✓ | — |
| Exportar e importar el XML de un escenario | Escritorio | ✓ | — | ✓ | — |
| Enviar una versión a revisión | Escritorio | ✓ | — | ✓ (la suya) | — |
| Aprobar o rechazar una versión | Web | ✓ (no la suya) | ✓ (no la suya) | — | — |
| Lanzar y cancelar corridas | Escritorio | ✓ | — | ✓ | — |
| Consultar corridas, resultados y comparación | Web | ✓ | ✓ | ✓ | — |
| Comparar con frontera y exportar el reporte | Escritorio | ✓ | — | ✓ | — |
| Subir el reporte de una comparación (`reports.upload`, D35) | Web, escritorio | ✓ | — | ✓ | — |
| Administrar cuentas y roles | Web | ✓ | — | — | — |
| Revocar teléfonos y sesiones | Servicios | ✓ | — | — | — |
| Consultar la bitácora de auditoría | Web | ✓ | — | — | — |

La app de escritorio solo deja entrar a ANALISTA y ADMINISTRADOR. En la app Android, la captura solo la ve el CAPTURISTA (RF-I19).

## Pendiente

- Hecho el 2026-11-22: la migración 034, los candados de la web por permiso (`requiere_permiso`; el CAPTURISTA solo entra al tablero y al mapa) y el retiro de `/reportes/nuevo`. Falta aplicar la 034 a la base de la máquina (`infra/aplica_migraciones.sh 034`).

## Operaciones que salieron

Recuperar la contraseña (RF-A10), publicar un escenario (RF-D09) y la configuración y los respaldos (RF-L06, RF-L08) ya no están en la matriz: sus requerimientos quedaron fuera de alcance. Corregir, validar y descartar un caso (RF-C11, RF-C15) regresaron con D47.
