# D35 - Expiración del token en el escritorio y archivo que recibe la web

Fecha: 2026-11-17 · Estado: Aceptada

## Contexto
Dos preguntas del bloque 0 del [checklist del tercer parcial](../parciales/parcial-3/checklist.md) que ninguna decisión cubría:

- **C10 (RF-H23):** si «validación del JWT» pide que el escritorio revise `exp`. Hoy la app no decodifica el token y renueva cuando un servicio responde `TOKEN_EXPIRADO`.
- **D-5 (RF-G16):** la rúbrica pide que la web reciba archivos, y hoy no recibe ninguno. La propuesta eran las evidencias de un caso, pero D1 quitó la captura de la web.

## Opciones consideradas
- `exp` en el escritorio: dejarlo como está, o leerlo y renovar antes de que venza.
- Archivo de la web: las evidencias de un caso o el reporte de una comparación.

## Decisión
- **`exp` en el escritorio (C10):** sí. La app lee `exp` sin verificar la firma, porque el secreto no va en el cliente, y renueva el token antes de que venza. La firma la siguen validando los servicios.
- **Archivo de la web (D-5):** el reporte de una comparación. Lo sube el ANALISTA o el ADMINISTRADOR, con el permiso nuevo `reports.upload`. Se valida por su contenido, su tamaño y su huella (RNF-C09) y va al bucket. El escritorio también lo sube (RF-F17): los dos caminos usan la misma tabla de metadatos y la misma interfaz de archivos.

## Consecuencias
- `reports.upload` se crea en la migración 034, junto con los cambios de D1.
- La interfaz de archivos (bloque D) tiene que quedar donde la web también la pueda importar. Hoy la web no importa `epidemia_comun`.
- Las evidencias en la web quedan fuera: la captura y sus fotos son de la app móvil (D1).

Depende de: D1, D30
