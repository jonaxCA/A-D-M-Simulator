# D20 - Migración gradual del monolito con fachada en la web

Fecha: — · Estado: Aceptada (2026-11-08)

## Contexto
`decisiones/todo.md` la listaba como «por registrar o confirmar». Hoy el monolito va directo a PostgreSQL y no llama a los microservicios; el profesor lo confirmó (§9.1 de la v2) y la rúbrica pide que la web siga funcionando de forma independiente.

## Opciones consideradas
- Opción A: la web sigue directa a PostgreSQL.
- Opción B: la web pasa módulo por módulo a consumir los servicios mediante una fachada.

## Decisión
Opción A: la web sigue pudiendo conectarse directamente a PostgreSQL.

## Consecuencias
Con la opción B la web dependería de los servicios y dejaría de ser independiente. Con la A hay dos caminos al mismo dato (web y servicios), así que las reglas de negocio no pueden vivir solo en uno.
