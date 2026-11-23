SET client_encoding = 'UTF8';

-- Corre los casos de demostracion hacia el presente: el caso mas reciente queda
-- en current_date y todas las demas fechas se mueven los mismos dias.
-- Las pantallas miran "los ultimos N dias" con current_date, y la semilla
-- (gen_demo_data.py) fija el "hoy" en 2026-09-03, asi que con los dias la demo
-- se queda sin graficas. Es idempotente: si ya esta al dia, no cambia nada.
--
--   psql "$DATABASE_URL" -f datos/scripts/refresca_fechas_demo.sql
--
-- Solo para la base de demostracion: con casos reales moveria sus fechas.
BEGIN;

WITH d AS (
    SELECT current_date - max(report_date) AS n, max(report_date) AS antes FROM cases
), a AS (
    UPDATE cases c
       SET report_date = c.report_date + d.n,
           onset_date  = c.onset_date + d.n,
           created_at  = c.created_at + d.n * interval '1 day',
           synced_at   = c.synced_at + d.n * interval '1 day'
      FROM d
     WHERE d.n <> 0
    RETURNING 1
)
INSERT INTO audit_log (action, entity_type, data_before, data_after)
SELECT 'UPDATE', 'cases',
       jsonb_build_object('ultimo_caso', d.antes),
       jsonb_build_object('ultimo_caso', current_date, 'dias_movidos', d.n,
                          'casos', (SELECT count(*) FROM a))
  FROM d
 WHERE d.n <> 0;

COMMIT;
