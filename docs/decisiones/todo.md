Decisiones por registrar o confirmar:

1. Migraciones SQL numeradas en lugar de Alembic.
2. Una sola instancia de PostgreSQL con un rol por servicio: cada servicio lee todo y escribe solo sus tablas.
3. Redis sin datos autoritativos: PostgreSQL es la fuente de verdad.
4. Migración gradual del monolito con fachada en la web, módulo por módulo.
5. XML por defecto y JSON con ?format=json o Accept: application/json.
6. Rutas en inglés y nombres de servicios en español.
7. FLAME GPU para el motor acelerado, con el motor de referencia en Python como respaldo.
