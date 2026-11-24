SET client_encoding = 'UTF8';
-- =============================================================================
-- 065_sincroniza_lote.sql
-- Dominio: simulacion. El estado de un lote sigue al de su corrida (E8, D37).
--
-- - corridas (cancelar y reintentar) y simulador (ejecutar, completar, fallar y
--   reencolar) llevaban cada uno su copia de _sincroniza_lote: el mismo UPDATE
--   de simulation_batches en la misma transaccion que el cambio de la corrida.
--   La regla queda una sola vez, en la base: un trigger AFTER UPDATE OF status
--   sobre simulation_runs pone al lote el estado de su corrida y, si es
--   terminal, su finished_at. Corre en la misma transaccion, como antes.
-- - SECURITY INVOKER: corre con los permisos de quien cambia la corrida.
--   svc_corridas y svc_simulador ya tienen UPDATE (status, finished_at) sobre
--   simulation_batches (029); ningun otro rol cambia el estado de una corrida.
-- - Es la 065, asignada por el lider a E (2026-11-23). Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION fn_sincroniza_lote()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE simulation_batches
    SET status = NEW.status,
        finished_at = CASE WHEN NEW.status IN ('completado', 'fallido', 'cancelado')
                           THEN NEW.finished_at END
    WHERE id = NEW.batch_id;
    RETURN NULL;
END;
$$;

COMMENT ON FUNCTION fn_sincroniza_lote() IS
    'El lote toma el estado de su corrida y, si es terminal, su finished_at (E8, D37). Antes era _sincroniza_lote, copiado en corridas y simulador.';

DROP TRIGGER IF EXISTS tg_simulation_runs_sincroniza_lote ON simulation_runs;
CREATE TRIGGER tg_simulation_runs_sincroniza_lote
    AFTER UPDATE OF status ON simulation_runs
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION fn_sincroniza_lote();

INSERT INTO schema_migrations (version, description)
VALUES ('065', 'Simulacion: el estado del lote sigue al de su corrida con un trigger (E8, D37)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
