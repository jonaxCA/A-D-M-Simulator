> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-E: Usabilidad

Lo que se le pide a las tres interfaces. Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-E01 | Toda la interfaz está en español | La web, la app Android y la de escritorio muestran sus textos y sus errores en español | Web, Móvil, Escritorio | Hecho |
| RNF-E03 | La web se adapta al tamaño de la pantalla | El tablero y el mapa se leen en un teléfono | Web | Verificar |
| RNF-E06 | Los errores se explican | Cada cliente dice qué pasó y qué se puede hacer, sin mostrar la traza (ver RF-H24 y RF-I22) | Web, Móvil, Escritorio | Verificar |
| RNF-E08 | Cada aplicación tiene su manual de usuario | Hay un manual por aplicación en [`docs/manuales/`](../../manuales/) | Web, Móvil, Escritorio | En parte: está el del escritorio; faltan el de la web y el de la móvil |
| RNF-E11 | La app móvil dice siempre si hay conexión | Ver RF-I20 | Móvil | Hecho |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-E02 | Misma paleta y tipografía en los tres clientes | No hay con qué comprobarlo |
| RNF-E04 | Accesibilidad básica | No lo pide la rúbrica |
| RNF-E05 | Confirmación visual en menos de 1 s | Se cubre con las metas de RNF-A |
| RNF-E07 | Uso de la app móvil sin entrenamiento | No hay con qué comprobarlo |
| RNF-E09 | Ayuda en los campos complejos | Ningún proceso lo pide |
| RNF-E10 | Atajos de teclado en el escritorio | Ningún proceso lo pide |
| RNF-E12 | Carga progresiva de datos grandes | Ningún proceso lo pide |
| RNF-E13 | Botones de 48 dp o más | No hay con qué comprobarlo |
| RNF-E14 | Preparado para otros idiomas | El sistema es solo en español |
