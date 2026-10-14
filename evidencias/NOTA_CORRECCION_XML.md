# Evidencia de corrección XML — 13 oct 2026

La conversión XML se actualizó en `microservicios/comun/epidemia_comun/formatos.py`. Las claves de bandas de edad que no pueden ser etiquetas XML (por ejemplo `0-19`, `80+`) ahora viajan en un atributo `clave` dentro de `<entrada>`, y `de_xml()` reconstruye los nombres originales.

**Pruebas relacionadas:**
- `microservicios/comun/tests/test_xml_claves_edad.py` (nuevas regresiones).
- `microservicios/enfermedades/tests/test_enfermedades.py` (bandas en catálogo).
- `microservicios/parametros/tests/test_parametros.py` (letalidad por edad).
- `microservicios/poblacion/tests/test_poblacion.py` (grupos de edad).

**Ejecución registrada tras el cambio:** `307 passed, 34 subtests passed in 1.64s`, en `evidencias/pruebas/pytest_microservicios_xml_corregido.txt`.

**Integración:** PR #115, fusionado en `feat/segundo-parcial-grupo-2pm`, commit `215b4a5`.

Estas pruebas validan el XML y el comportamiento unitario cubierto. No equivalen a pruebas del despliegue final de los 26 servicios.
