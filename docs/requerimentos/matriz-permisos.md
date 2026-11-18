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

La app de escritorio solo deja entrar a ANALISTA y ADMINISTRADOR. La app Android todavía muestra el mismo menú a cualquier rol (RF-I19).

## Pendiente

- **Migración 034:** crea `scenarios.approve`, lo da a EPIDEMIOLOGO y ADMINISTRADOR, quita `audit.read` al EPIDEMIOLOGO, quita `cases.create` al ADMINISTRADOR y crea `reports.upload` (D35). No está aplicada (ver [`decisiones/todo.md`](../decisiones/todo.md), «Cambios pendientes por D1»).
- **Candados de la web contra esta matriz:** hoy el monitoreo epidemiológico y las exportaciones solo piden sesión, así que el CAPTURISTA también entra. Falta limitarlo al tablero y al mapa (RF-G11).
- **La captura de casos en la web** (`/reportes/nuevo`) sigue en el código; D1 la quita.

## Operaciones que salieron

Recuperar la contraseña (RF-A10), corregir, confirmar o descartar un caso (RF-C11, RF-C15), publicar un escenario (RF-D09) y la configuración y los respaldos (RF-L06, RF-L08) ya no están en la matriz: sus requerimientos quedaron fuera de alcance.
