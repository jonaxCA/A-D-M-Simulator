# D53 - Importación de series observadas: el servicio `importacion`

Fecha: 2026-11-22 · Estado: Aceptada · Atiende RF-B08 (reabierto) y RF-C16 · Amplía D50 (migración 061) · Aplica D43 y D52

## Contexto
- La retroalimentación pide que el escritorio pueda «importar conjuntos autorizados, verificar
  calidad, examinar series y registrar versiones» (`RETROALIMENTACION_SEGUNDO_PARCIAL.txt`, l. 181).
  Además sugiere un servicio `importacion-datos` (l. 117). El checklist lo deja en D6 (RF-B08,
  reabierto), y A4 lo espera.
- D50 decidió calibrar contra una serie pública agregada y crear `observed_datasets` y
  `observed_points` en la 061. Esas tablas se llenan de dos formas: la serie de D50 llega por
  migración y las demás, por «el importador de D6».
- Ningún servicio del catálogo tiene esa tarea. `poblacion` carga el censo, que es otro dato y
  tiene otro dueño. `calibracion` (E7) todavía no existe y su tarea es calibrar.
- RNF-I05 y D50 no admiten registros por persona: solo conteos agregados con licencia de libre uso.

## Opciones consideradas
- **Dónde:** A) un servicio nuevo, `importacion`; B) una ruta en `poblacion`; C) solo la migración,
  y el importador después de `calibracion`.
- **Permiso para importar:** A) un permiso nuevo para EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR; B) solo
  EPIDEMIOLOGO y ADMINISTRADOR.
- **Ventana de la serie de D50:** A) la 061 trae solo la ventana, fijada por una regla; B) trae todo
  2020 y `calibracion` elige.

## Decisión
Dónde A, permiso A y ventana A, decididas con el líder el 2026-11-22.

**El servicio `importacion`** es el n.º 31 del catálogo: el 30 queda para `calibracion` (D50). Usa
el puerto 5226 y el perfil `vigilancia`, parte de `epidemia/base-vigilancia` (E8) y su rol es
`svc_importacion`, dueño de las dos tablas.

| Ruta | Qué hace | Roles |
|---|---|---|
| `POST /api/v1/datasets` | Revisa e importa: 201 con la versión siguiente, 200 si ese archivo ya estaba con esa clave, 422 si no pasa | EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR (`datasets.upload`) |
| `POST /api/v1/datasets/validate` | La misma revisión sin guardar, con todas las fallas | los mismos |
| `GET /api/v1/datasets`, `GET /api/v1/datasets/{id}`, `GET /api/v1/datasets/{id}/points` | Lista, detalle con resumen y la serie | los de `simulations.read`, como en D50 |

**El archivo** va tal cual en el cuerpo, en CSV, JSON o XML (este último validado contra
`serie_observada.xsd`). Los metadatos van en la consulta, como en `POST /reports` de `evidencias`.
Excel queda fuera, porque el checklist pide CSV, JSON y XML.

**La revisión:**
- **Solo agregados:** cada punto lleva `periodo_inicio` y `valor`, y una columna de más se rechaza
  (RNF-I05).
- **Valores:** fechas válidas y enteros no negativos, de 4 a 5 000 puntos.
- **Periodos:** seguidos, sin repetirse ni dejar huecos; un periodo sin casos se escribe con 0.
- **Metadatos:** enfermedad y región que existen, métrica (`casos_confirmados`, `hospitalizaciones`
  o `defunciones`), periodo (`semana` o `dia`), fuente y licencia. El corte no puede ser futuro ni
  anterior al último periodo.

**Versiones:**
- Cada conjunto tiene una clave (`code`). Importar otra vez la misma clave crea la versión
  siguiente.
- El mismo archivo (la misma SHA-256) con la misma clave regresa la versión que ya estaba, así que
  el cliente puede reintentar.
- Nada se edita ni se borra (D52): `svc_importacion` solo tiene SELECT e INSERT.

**Permiso:**
- `datasets.upload`, para EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR, los mismos que lanzan una
  calibración (D50): quien calibra necesita importar su serie.
- Se iba a llamar `datasets.import`, pero `permissions` exige que el código sea `recurso.acción`, y
  agregar la acción `import` haría fallar la 034 al volver a correr el dump, porque la 034 rehace
  ese CHECK y no se edita (D7). Por eso usa la acción `upload`, como `reports.upload`.

**Alcance (D43):** importar exige que la región esté en el alcance de la cuenta. La lista y la
consulta solo muestran las regiones que cubre.

**La serie de D50:** la 061 la carga con la clave `COVID19_NL_2020_SINTOMAS`, versión 1. La genera
`datos/scripts/build_serie_observada.py` desde `datos/observados/covid19_nl_2020_semanal.csv`.
- **Fuente:** el cierre anual 2020 de los datos abiertos de COVID-19 de la DGE
  (`COVID19MEXICO2020.zip`). Su corte es el 2021-10-31 (`FECHA_ACTUALIZACION`) y su SHA-256,
  `64c90685…8dab90`.
- **Filtro:** `ENTIDAD_RES` = 19 y `CLASIFICACION_FINAL` 1 a 3. Así lo dice el catálogo
  `CLASIFICACION_FINAL_COVID` del diccionario vigente (2024-07-08), que cambió el nombre del campo.
- **Licencia:** el decreto de datos abiertos (DOF del 20-02-2015, art. 5, fr. III): «De libre uso:
  Citarán la fuente de origen como único requerimiento para ser utilizados libremente». La DGE lo
  invoca en su aviso de históricos. No se pudo consultar datos.gob.mx (rechaza las descargas
  automáticas), así que se cita el decreto.
- **Semanas:** epidemiológicas, de domingo a sábado, por `FECHA_SINTOMAS`. El cierre 2021 no trae
  casos de Nuevo León con inicio en 2020, así que el de 2020 está completo para ese año.
- **La ventana, por regla:** empieza en la primera semana con casos. El pico de la primera ola es la
  primera semana seguida de tres descensos, y la ventana termina en el valle: la semana con menos
  casos después del pico, entre las semanas completas de 2020. Si el valle cayera en las últimas
  cuatro semanas del archivo, el script se detiene.
- **Resultado:** del 2020-03-01 al 2020-07-26, 22 semanas con 22 259 casos, pico en la del
  2020-07-05 (3 295).

## Consecuencias
- RF-B08 y RF-C16 quedan hechos. El escritorio (A4) ya tiene contra qué construir «Gestión de datos»,
  y `calibracion` (E7) tiene su serie.
- El catálogo pasa a 30 servicios (31 con `calibracion`). Se agregan una entrada en el compose,
  nginx y el directorio de `estado-servicios`, y una contraseña más (`DB_PASSWORD_IMPORTACION`) en
  `infra/.env`. En una base que ya existe, hay que correr la 061 y la 063.
- **El valle no separa dos olas limpias.** En Nuevo León, después del valle del 2020-07-26, la serie
  se queda en una meseta de unos 2 200 a 2 800 casos por semana. Sube en octubre y noviembre, y
  2020 termina alto. La ventana cubre el crecimiento, el pico y la primera bajada. Las últimas ⅓
  semanas, que validan (D50), son las del pico: es una prueba exigente para el modelo.
- **Para E (062):** `svc_calibracion` necesita SELECT en `observed_datasets` y `observed_points`.
  Como la 061 ya estará integrada, la 062 puede otorgarlo.
- **Para quien rehaga el CHECK de acciones de `permissions`:** tiene que conservar `upload`.

Depende de: D43, D50, D52

## Fuentes
- `docs/parciales/parcial-3/RETROALIMENTACION_SEGUNDO_PARCIAL.txt` (l. 117 y 181) y el checklist
  (D6, A4).
- DGE, cierre anual 2020:
  https://datosabiertos.salud.gob.mx/gobmx/salud/datos_abiertos/historicos/2020/COVID19MEXICO2020.zip
- DGE, diccionario de datos:
  https://datosabiertos.salud.gob.mx/gobmx/salud/datos_abiertos/diccionario_datos_abiertos.zip
- DGE, aviso de datos abiertos históricos:
  https://www.gob.mx/cms/uploads/attachment/file/1101086/cierre_datos_abiertos_historicos_2025.pdf
- Decreto por el que se establece la regulación en materia de Datos Abiertos, DOF del 20-02-2015:
  https://dof.gob.mx/nota_detalle.php?codigo=5382838&fecha=20/02/2015
