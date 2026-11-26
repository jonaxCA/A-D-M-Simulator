# D61 - Licencias: MIT para el repositorio y AGPL-3.0 para `abm-gpu`

Fecha: 2026-11-25 · Estado: Propuesta (falta que las siete personas den su visto bueno)

## Contexto
El repositorio es público en GitHub y no tiene licencia. Sin licencia, el código queda con todos los derechos reservados: GitHub deja verlo y hacerle fork, pero nadie puede usarlo, modificarlo ni redistribuirlo. Cada integrante es dueño de lo que escribió, así que la licencia la deciden todas las personas que han programado (las que lista `README.md`).

`abm-gpu` (D23) usa FLAME GPU 2, que es AGPL-3.0. `procesamiento/abm_gpu/entorno.py` importa `pyflamegpu` en el mismo proceso que el trabajador del simulador, y la FSF considera eso una obra combinada:
- Si se distribuye (por ejemplo, la imagen de `microservicios/simulador/gpu.Dockerfile`, que trae la rueda de `pyflamegpu`), se distribuye completa bajo AGPL y con su código fuente.
- Por la sección 13 de la AGPL, a quien usa el programa por la red (las corridas de `abm-gpu` que se lanzan en https://epidemos.app) se le ofrece el código fuente. Se discute si aplica cuando FLAME GPU no se modifica; se toma la lectura prudente.

El resto (sitio, escritorio, app móvil, `seir-ref`, `abm-ref`, los demás servicios) son programas aparte que hablan con el simulador por Redis o HTTP, y no cargan `pyflamegpu`: `entorno.py` lo importa hasta que se simula con `abm-gpu`.

## Opciones consideradas
- A) Todo el repositorio bajo AGPL-3.0.
- B) El repositorio bajo MIT y `procesamiento/abm_gpu/` bajo AGPL-3.0.
- C) Quitar `abm-gpu` y quedarse con `abm-ref`.

## Decisión
B. MIT es compatible con la AGPL: el código MIT se puede combinar con FLAME GPU, y la obra combinada (el simulador cuando corre `abm-gpu`) se distribuye bajo AGPL-3.0. Así se cumple con FLAME GPU sin volver copyleft el sitio, las apps ni los demás servicios. C tira un motor que ya funciona (D23), y A obliga a todo el proyecto por una sola carpeta.

- `LICENSE` en la raíz: MIT, con la excepción de `procesamiento/abm_gpu/`.
- `procesamiento/abm_gpu/LICENSE`: el texto de la AGPL-3.0, el mismo de FLAME GPU 2.
- `README.md` y `procesamiento/abm_gpu/README.md` dicen qué licencia tiene cada parte.

## Consecuencias
- Cualquiera puede usar y reutilizar el proyecto con la licencia MIT, conservando el aviso de copyright.
- Lo que se agregue a `procesamiento/abm_gpu/`, y cualquier copia del simulador que cargue `pyflamegpu`, queda bajo AGPL-3.0: no se puede volver privado.
- Si se publica la imagen del simulador de GPU en un registro, va con el código fuente o con un enlace a este repositorio en la versión que se publicó.
- Pendiente: para cumplir la sección 13, el sitio y el escritorio enlazan al código fuente (este repositorio). Hoy ninguno lo hace.
- No cambia la licencia de Highcharts: es gratis para uso académico y no comercial, no para un sitio comercial.

Depende de: D23
