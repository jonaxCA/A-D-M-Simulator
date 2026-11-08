Estado: por confirmar. 

### Leyenda

- ✓ acceso completo a la operación.
- RO (readonly) solo lectura: puede consultar; no crea, edita, ejecuta ni exporta.
- — sin acceso.
- ✓\* con restricción. La restricción está pendiente de definir en D1.

### Matriz de permisos por operación

| Operación                           | Admin | Epid. | Analista | Capturista |
| :----                               | :---- | :---- | :----    | :----      |
| Iniciar/cerrar sesión               | ✓     | ✓     | ✓        | ✓          |
| Recuperar contraseña                | ✓     | ✓     | ✓        | ✓          |
| Gestiónar usuarios y roles          | ✓     | —     | —        | —          |
| Revocar dispositivos / sesiónes     | ✓     | —     | —        | —          |
| Consultar auditoría                 | ✓     | —     | —        | —          |
| Configuración / respaldos           | ✓     | —     | —        | —          |
| Gestiónar catálogos                 | ✓     | ✓     | RO       | RO         |
| Registrar casos                     | —     | —     | —        | ✓          |
| Adjuntar evidencia / escanear lotes | —     | —     | —        | ✓          |
| Registrar vacunación                | —     | —     | —        | ✓          |
| Corregir caso                       | —     | ✓     | —        | ✓\*        |
| Confirmar o descartar caso          | —     | ✓     | —        | —          |
| Crear / editar escenario            | —     | —     | ✓        | —          |
| Aprobar / rechazar escenario        | —     | ✓     | —        | —          |
| Publicar escenario                  | —     | ✓\*   | —        | —          |
| Ejecutar simulación                 | —     | —     | ✓\*      | —          |
| Configurar réplicas / motor         | —     | —     | ✓        | —          |
| Cancelar simulación                 | —     | —     | ✓        | —          |
| Consultar progreso                  | RO    | RO    | ✓        | —          |
| Consultar resultados internos       | RO    | ✓     | ✓        | —          |
| Comparar escenarios                 | —     | ✓     | ✓        | —          |
| Exportar resultados / reportes      | —     | ✓     | ✓        | —          |
| Consultar tablero web               | RO    | ✓     | RO       | —          |
| Consultar información publica       | ✓     | ✓     | ✓        | ✓          |
| Monitoreo técnico                   | ✓     | —     | —        | —          |
