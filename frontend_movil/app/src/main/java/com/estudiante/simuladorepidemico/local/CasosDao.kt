package com.estudiante.simuladorepidemico.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

const val MAXIMO_POR_LOTE = 100

// Los métodos abiertos llevan la lógica y Room los corre en una transacción; las pruebas locales
// usan un DAO falso que solo reemplaza las consultas.
@Dao
abstract class CasosDao {
    @Insert
    abstract suspend fun insertar(caso: CasoLocal)

    @Query("SELECT * FROM casos WHERE cuenta = :cuenta ORDER BY capturadoEn DESC, localUuid")
    abstract fun deLaCuenta(cuenta: Long): Flow<List<CasoLocal>>

    @Query("SELECT COUNT(*) FROM casos WHERE cuenta = :cuenta AND estado = 'PENDIENTE'")
    abstract fun porEnviar(cuenta: Long): Flow<Int>

    @Query("SELECT lote FROM casos WHERE cuenta = :cuenta AND lote IS NOT NULL LIMIT 1")
    abstract suspend fun loteAbierto(cuenta: Long): String?

    @Query(
        """UPDATE casos SET lote = :lote WHERE localUuid IN (
               SELECT localUuid FROM casos WHERE cuenta = :cuenta AND estado = 'PENDIENTE' AND lote IS NULL
               ORDER BY capturadoEn, localUuid LIMIT :maximo)"""
    )
    abstract suspend fun asignarLote(cuenta: Long, lote: String, maximo: Int): Int

    @Query("SELECT * FROM casos WHERE lote = :lote ORDER BY capturadoEn, localUuid")
    abstract suspend fun delLote(lote: String): List<CasoLocal>

    // Ya está en el servidor: del teléfono se borra lo que identifica a la persona y queda el
    // comprobante (enfermedad, municipio, fecha y case_id).
    @Query(
        """UPDATE casos SET estado = 'ENVIADO', caseId = :caseId, lote = NULL, error = NULL,
               inicioSintomas = NULL, edad = NULL, sexo = NULL, resultadoPrueba = NULL,
               severidad = NULL, latitud = NULL, longitud = NULL
           WHERE localUuid = :localUuid"""
    )
    abstract suspend fun marcarEnviado(localUuid: String, caseId: Long?)

    @Query("UPDATE casos SET estado = 'RECHAZADO', error = :error, lote = NULL WHERE localUuid = :localUuid")
    abstract suspend fun marcarRechazado(localUuid: String, error: String)

    @Query("UPDATE casos SET lote = NULL WHERE lote = :lote")
    abstract suspend fun soltar(lote: String)

    @Query("DELETE FROM casos WHERE localUuid = :localUuid AND estado = 'RECHAZADO'")
    abstract suspend fun descartar(localUuid: String)

    // El lote que quedó sin respuesta, con los mismos casos, o uno nuevo con los pendientes más
    // viejos. null si no hay nada que mandar.
    @Transaction
    open suspend fun siguienteLote(cuenta: Long, nuevo: String, maximo: Int = MAXIMO_POR_LOTE): Lote? {
        val lote = loteAbierto(cuenta) ?: nuevo.takeIf { asignarLote(cuenta, it, maximo) > 0 } ?: return null
        return Lote(lote, delLote(lote))
    }

    // Lo que el lote no resolvió (teléfono revocado, o un caso sin resultado) vuelve a pendiente y
    // sale en un lote nuevo: reenviar este regresaría el mismo resultado guardado.
    @Transaction
    open suspend fun aplicar(lote: String, enviados: Map<String, Long?>, rechazados: Map<String, String>) {
        enviados.forEach { (localUuid, caseId) -> marcarEnviado(localUuid, caseId) }
        rechazados.forEach { (localUuid, error) -> marcarRechazado(localUuid, error) }
        soltar(lote)
    }
}
