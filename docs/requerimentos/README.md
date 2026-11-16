> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# Requerimientos de la v3

Es el paso 5 del orden de trabajo de [`brechas_v3.md`](../arquitectura/brechas_v3.md) (§10 y §9.6). Los requerimientos salen de los tres procesos ([`procesos_v3.md`](../arquitectura/procesos_v3.md)), de las matrices ([`matrices_v3.md`](../arquitectura/matrices_v3.md)), de la arquitectura ([`arquitectura_v3.md`](../arquitectura/arquitectura_v3.md)) y de las decisiones D1 a D32 ([`decisiones.md`](../decisiones/decisiones.md)). Si un requerimiento contradice una decisión, gana la decisión.

## Qué hay aquí

| Documento | Qué tiene |
|---|---|
| [`funcionales/`](funcionales/) | Un archivo por módulo, de RF-A a RF-L |
| [`no-funcionales/`](no-funcionales/) | Un archivo por categoría, de RNF-A a RNF-L |
| [`historias-usuario.md`](historias-usuario.md) | Una historia por paso de proceso, con su criterio de aceptación |
| [`reglas-negocio.md`](reglas-negocio.md) | Las reglas RN-01 a RN-40 |
| [`matriz-permisos.md`](matriz-permisos.md) | Qué puede hacer cada rol (D1) |
| [`trazabilidad.md`](trazabilidad.md) | Paso de proceso, requerimiento, componente, servicio y prueba |

Los casos de uso principales son los tres procesos: P1 (captura en campo), P2 (diseño y aprobación de escenarios) y P3 (simulación y comparación). No se repiten aquí.

## Módulos funcionales

| Módulo | Dónde entra |
|---|---|
| [RF-A](funcionales/rf-a-autenticacion.md) Autenticación | Soporte; pasos 1.1 y 2.1 |
| [RF-B](funcionales/rf-b-catalogos.md) Catálogos | Soporte; pasos 1.3 y 2.2 |
| [RF-C](funcionales/rf-c-vigilancia.md) Vigilancia | P1 |
| [RF-D](funcionales/rf-d-escenarios.md) Escenarios | P2 |
| [RF-E](funcionales/rf-e-simulacion.md) Simulación | P3 |
| [RF-F](funcionales/rf-f-resultados.md) Resultados | P3 |
| [RF-G](funcionales/rf-g-tablero-web.md) Tablero web | La visualización de P1 y P3 |
| [RF-H](funcionales/rf-h-app-escritorio.md) App de escritorio | P2 y P3 |
| [RF-I](funcionales/rf-i-app-android.md) App Android | P1 |
| [RF-J](funcionales/rf-j-publicacion.md) Sitio público | Soporte |
| [RF-K](funcionales/rf-k-monitoreo.md) Monitoreo | Soporte |
| [RF-L](funcionales/rf-l-administracion.md) Administración | Soporte |

## Cómo leer las tablas

- **ID:** se conserva el de siempre para no romper la trazabilidad. Un requerimiento nuevo toma el siguiente número libre de su módulo. Un ID retirado no se vuelve a usar: queda en «Fuera de alcance», con su motivo.
- **Criterio de aceptación:** lo que se puede comprobar. En los pasos de proceso sale de las columnas *Escribe en*, *Auditoría* y *Notifica a*.
- **Paso:** el paso de `procesos_v3.md` (1.4, 3.2…), o «Soporte» si no pertenece a un proceso.
- **Componente:** la clasificación que pide la rúbrica: Web, Microservicios, Móvil, Escritorio, Bases de datos, Infraestructura, Seguridad o Monitoreo.
- **Prioridad:** Alta si lo pide la rúbrica o un proceso no termina sin él; Media si mejora un proceso; Baja si puede esperar.
- **Estado:**
  - **Hecho:** está en el código.
  - **En parte:** una parte está hecha; el texto dice cuál falta.
  - **Falta:** está decidido y no implementado. Lleva su brecha de `brechas_v3.md` o su decisión.
  - **Por decidir:** el equipo no ha decidido; no se implementa sin preguntar.
  - **Verificar:** no se confirmó leyendo el código; alguien tiene que probarlo.

No se inventan cifras. Una meta de rendimiento sin medición dice «por confirmar con Locust».
