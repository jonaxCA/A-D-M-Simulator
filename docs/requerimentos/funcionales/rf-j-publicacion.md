> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-J: Sitio público

Función de soporte: la página de la web que se ve sin iniciar sesión. Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- PostgreSQL: `cases`, `diseases`, `regions`.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-J01 | La web tiene una página pública, sin sesión | La raíz del sitio abre sin iniciar sesión, y ofrece el enlace para entrar. Con sesión, lleva al tablero | Soporte | Web | Media | Hecho |
| RF-J03 | La página pública muestra indicadores agregados y la curva de los últimos 30 días | No se ve ningún caso individual ni su ubicación | Soporte | Web, Seguridad | Media | Hecho |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-J02 | Mostrar los escenarios publicados | Ninguna pantalla ni servicio publica escenarios (ver RF-D09) |
| RF-J04 | Leyenda de proyecto académico en toda publicación | El aviso que sí existe es el de los resultados: no son una predicción (RF-F19) |
| RF-J05 | Supuestos y limitaciones junto a cada escenario publicado | Depende de RF-J02 |
| RF-J06 | Notas de versión de los datos | Ningún proceso lo pide |
| RF-J07 | Banda de incertidumbre en las gráficas públicas | La página pública muestra casos capturados, no simulaciones. La banda está en la comparación (RF-F06) |
| RF-J08 | Gráficas en alta resolución para prensa | Ningún proceso lo pide |
