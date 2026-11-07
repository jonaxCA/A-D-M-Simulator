package com.estudiante.simuladorepidemico.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

enum class EstadoCaso { PENDIENTE, ENVIADO, RECHAZADO }

// Un caso capturado en el teléfono, con los campos de POST /api/v1/cases. Es de la cuenta que lo
// capturó y solo se manda con una sesión suya: reported_by sale del token. Mientras `lote` no es
// null, el caso va en un lote que se mandó y no ha respondido, y se reenvía con el mismo batch_id.
@Entity(tableName = "casos", indices = [Index("cuenta", "estado"), Index("lote")])
data class CasoLocal(
    @PrimaryKey val localUuid: String,
    val cuenta: Long,
    val enfermedad: Long,
    val municipio: Long,
    val fechaReporte: String,
    val inicioSintomas: String? = null,
    val edad: Int? = null,
    val sexo: String? = null,
    val resultadoPrueba: String? = null,
    val severidad: String? = null,
    val latitud: Double? = null,
    val longitud: Double? = null,
    val capturadoEn: Long,
    val estado: EstadoCaso = EstadoCaso.PENDIENTE,
    val lote: String? = null,
    val caseId: Long? = null,
    val error: String? = null,
)

data class Lote(val id: String, val casos: List<CasoLocal>)
