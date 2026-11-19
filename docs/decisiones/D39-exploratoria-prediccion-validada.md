# D39 - Simulación exploratoria, predicción y resultado validado

Fecha: 2026-11-19 · Estado: Aceptada (tomada en sesión por el equipo del salón 2; falta validarla con el líder) · Amplía la regla 9 del `AGENTS.md` de la raíz

## Contexto
La retroalimentación pide distinguir con claridad entre simulaciones exploratorias, predicciones y resultados validados, y recuerda que una curva no demuestra que el modelo sea correcto. Hoy todas las pantallas muestran el mismo `AVISO_SIMULACION`, que solo dice que no es una predicción.

## Opciones consideradas
- Opción A: un texto fijo más largo en cada pantalla.
- Opción B: cada corrida trae su categoría, calculada por el servidor con reglas explícitas, y la pantalla la muestra con su explicación.

## Decisión
Opción B, para que la categoría dependa del modelo y de los datos, no de lo que escriba cada cliente.

**Las tres categorías:**

| Categoría | Cuándo | Hoy |
|---|---|---|
| `exploratoria` | Todo lo que no cumple las otras dos. Sirve para comparar escenarios entre sí («qué pasa si»), no para anticipar cifras reales. | Todas las corridas |
| `prediccion` | El modelo y su versión están calibrados contra una serie observada de esa enfermedad y región, la corrida empieza en el estado observado y trae intervalo de incertidumbre. | Ninguna: no hay calibración |
| `validada` | Además de lo anterior, la versión del modelo reprodujo datos observados que no se usaron para calibrar, dentro de la tolerancia que declara su ficha. | Ninguna |

**Verificar no es validar.** Las pruebas contra resultados esperados (tamaño final del SEIR, casos límite, `abm-ref` contra `seir-ref`) muestran que el modelo es matemáticamente consistente: es un modelo *verificado*. Eso no sube una corrida de `exploratoria`, pero se muestra junto a ella («modelo verificado: sí, ver ficha»).

**Dónde vive:**
- El estado de cada modelo y versión (verificado, calibrado y validado, con su enfermedad y región) se registra en `procesamiento/estado_validacion.json`. Cada estado enlaza a su evidencia en `docs/arquitectura/ficha_simulador.md`.
- `resultados` regresa `categoria`, `modelo_verificado` y `motivo` con cada corrida. Una corrida con algún parámetro marcado como supuesto o sin fuente nunca pasa de `exploratoria`.
- La web (C) y el escritorio (A) muestran la categoría con su texto en cada pantalla y en cada gráfica de resultados. `AVISO_SIMULACION` se convierte en el texto de `exploratoria`.

## Consecuencias
- La categoría es una regla de negocio de `resultados` (D37).
- Mientras no haya calibración, todo se presenta como exploratorio, que es lo honesto.
- Subir un modelo a `prediccion` o `validada` exige cambiar el registro con su evidencia, en un PR revisado.
- Las pantallas de A y C cambian, cada una en la rama de su bloque.
