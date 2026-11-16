# D20 - La web sigue conectada directo a PostgreSQL, sin fachada hacia los servicios

Fecha: — · Estado: Aceptada (2026-11-08)

## Contexto
`decisiones/todo.md` la listaba como «por registrar o confirmar». Hoy el monolito va directo a PostgreSQL y no llama a los microservicios; el profesor lo confirmó (§9.1 de la v2) y la rúbrica pide que la web siga funcionando de forma independiente.

## Opciones consideradas
- Opción A: la web sigue directa a PostgreSQL.
- Opción B: migración gradual: la web pasa módulo por módulo a consumir los servicios mediante una fachada.

## Decisión
Opción A: la web sigue conectándose directamente a PostgreSQL. Con la opción B, la web dependería de los servicios y dejaría de ser independiente.

## Consecuencias
- Hay dos caminos al mismo dato (web y servicios), así que las reglas de negocio no pueden vivir solo en uno (ver `todo.md`).
- **Excepción (2026-11-16, por D28):** las curvas de una corrida. La serie diaria pasa a MongoDB (`series_corridas`), así que la web se las pide a `resultados`; es la única llamada de la web a un servicio. El resumen lo sigue leyendo directo de `simulation_runs`. Si `resultados` no responde, la pantalla muestra el resumen sin curvas.
- La fachada que propone `propuesta_correcciones_primer_parcial.md` (partir `queries.py`) solo ordena el código de la web; no cambia esta decisión.
