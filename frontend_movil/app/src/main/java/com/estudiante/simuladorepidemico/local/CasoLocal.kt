package com.estudiante.simuladorepidemico.local

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey
import com.estudiante.simuladorepidemico.red.json
import com.estudiante.simuladorepidemico.sesion.Cifrador
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

enum class EstadoCaso { PENDIENTE, ENVIADO, RECHAZADO }

// Un caso capturado en el teléfono, con los campos de POST /api/v1/cases. Es de la cuenta que lo
// capturó y solo se manda con una sesión suya: reported_by sale del token. Mientras `lote` no es
// null, el caso va en un lote que se mandó y no ha respondido, y se reenvía con el mismo batch_id.
// Los datos de salud van cifrados en `datos` (DatosDeSalud) con la llave del Keystore; las columnas
// de inicioSintomas a longitud solo las tienen los casos guardados antes de la versión 3 de la base.
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
    // La versión del formulario de su enfermedad con que se capturó (D48).
    val formulario: Long? = null,
    val datos: String? = null,
)

// Lo que identifica a la persona del caso. Se guarda cifrado y se borra al enviarse.
@Serializable
data class DatosDeSalud(
    val inicioSintomas: String? = null,
    val edad: Int? = null,
    val sexo: String? = null,
    val resultadoPrueba: String? = null,
    val severidad: String? = null,
    val latitud: Double? = null,
    val longitud: Double? = null,
    val respuestas: JsonObject? = null,
)

fun DatosDeSalud.cifrados(cifrador: Cifrador): String = cifrador.cifrar(json.encodeToString(this))

// Sin la llave del Keystore (app reinstalada) no se pueden leer: el caso sigue, sin esos datos.
fun CasoLocal.salud(cifrador: Cifrador): DatosDeSalud = datos
    ?.let { runCatching { json.decodeFromString<DatosDeSalud>(cifrador.descifrar(it)) }.getOrDefault(DatosDeSalud()) }
    ?: DatosDeSalud(inicioSintomas, edad, sexo, resultadoPrueba, severidad, latitud, longitud)

data class Lote(val id: String, val casos: List<CasoLocal>)

enum class EstadoFoto { PENDIENTE, SUBIDA, RECHAZADA }

// Una foto de un caso; el archivo es fotos/<id>.jpg (FotosEnDisco). Se sube a evidencias cuando el
// caso ya tiene case_id, y entonces el archivo se borra del teléfono. Si se descarta el caso, la
// foto se va con él.
@Entity(
    tableName = "fotos",
    foreignKeys = [
        ForeignKey(entity = CasoLocal::class, parentColumns = ["localUuid"], childColumns = ["caso"], onDelete = ForeignKey.CASCADE),
    ],
    indices = [Index("caso")],
)
data class FotoLocal(
    @PrimaryKey val id: String,
    val caso: String,
    val tomadaEn: Long,
    val estado: EstadoFoto = EstadoFoto.PENDIENTE,
    val evidencia: Long? = null,
    val error: String? = null,
)

data class FotoPorSubir(val id: String, val caseId: Long)

data class ConteoFotos(val caso: String, val total: Int, val subidas: Int, val rechazadas: Int)
