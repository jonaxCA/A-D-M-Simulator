# D57 - Prevalencia, hospitalizaciones y capacidad hospitalaria utilizada en el tablero

Fecha: 2026-11-23 · Estado: Aceptada (aprobada por el dueño del bloque F; pendiente de validación del líder) · Atiende RF-G07 (reabierto) y la retroalimentación de `indicadores` («incidencia, prevalencia cuando aplique, mortalidad, hospitalizaciones, capacidad utilizada») · Amplía F7

## Contexto
`indicadores` ya daba cada indicador con su numerador, su denominador y su periodo (F7), pero
faltaban tres: la capacidad utilizada no tenía fuente, la plataforma no registra hospitalizaciones
y la prevalencia necesita saber qué casos siguen activos, y los casos no tienen fecha de
recuperación. RF-G07 (ocupación hospitalaria) había quedado fuera de alcance por lo mismo.

## Opciones consideradas
- Camas: A) el cierre anual de Recursos en Salud Sectorial de la DGIS, por establecimiento (CLUES),
  datos abiertos; B) la Red IRAG (ocupación diaria real), que solo cubre infecciones respiratorias,
  se armó para la pandemia y no corresponde a los casos de la plataforma; C) dejarlo fuera.
- Dónde guardarlas: 1) una tabla y su migración; 2) un archivo de datos que la imagen de
  `indicadores` copia, como la geometría de `zonas`.
- Hospitalizados: i) un campo «hospitalizado» en la captura (cambia la app y la base); ii) estimarlos
  con la gravedad que ya se captura.

## Decisión
**A, 2 e ii.**

- **Camas censables:** las del área de hospitalización (el descriptor de la DGIS las llama
  censables) de los establecimientos del sector público de Nuevo León, en el cierre anual 2025 de
  Recursos en Salud Sectorial (corte 2025-12-31, publicado el 2026-09-23): 4 339 camas en 13 de los
  51 municipios. No incluye hospitales privados. Viven en `datos/capacidad/camas_censables_nl.csv`,
  por municipio, con la fuente, la URL, la licencia, el corte, el alcance y la huella SHA-256 del zip
  de la DGIS en su encabezado; lo genera `datos/scripts/build_camas_censables.py agrega <zip>` y no
  se edita a mano. El zip no entra al repositorio.
- **Supuestos, a la vista en cada numerador:** un caso sigue activo 14 días desde su reporte
  (`DIAS_ACTIVO`, la ventana de dos semanas que la consulta ya trae), y un caso con gravedad
  «grave» está hospitalizado y ocupa una cama censable ese tiempo.
- **Tres indicadores nuevos** en `indicadores` de `GET /dashboard/indicators`, con el mismo formato:
  - `prevalencia`: casos de los últimos 14 días por 100 000 habitantes de Nuevo León;
  - `hospitalizaciones`: casos graves de los últimos 14 días (estimadas);
  - `capacidad_utilizada`: esas hospitalizaciones entre las camas censables, en %.
- Cada indicador trae `fuente`: `null` si sale de los casos; en `capacidad_utilizada`, la de las
  camas (`documento`, `url`, `licencia`, `corte`, `alcance` y `sha256`). Sin el archivo, la
  capacidad sale sin valor en lugar de fallar.

## Consecuencias
- RF-G07 sale de «fuera de alcance»: el tablero tiene ocupación hospitalaria estimada, con su
  fuente y sus supuestos.
- Es una estimación: con casos sintéticos y sin dato de hospitalización no es la ocupación real.
  Si algún día se captura la hospitalización, el numerador cambia y el denominador se queda.
- Actualizar las camas es correr el script con el cierre siguiente de la DGIS y reconstruir
  `indicadores`; no hay migración.
- `umbral_saturacion_hospitalaria` (0.85, migración 010) podrá dar el semáforo de este indicador
  cuando el tablero lo pinte; hoy la web solo lee los campos de siempre.
