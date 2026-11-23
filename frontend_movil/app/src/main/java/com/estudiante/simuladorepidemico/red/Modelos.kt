package com.estudiante.simuladorepidemico.red

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class Servicio(val nombre: String, val url: String)

@Serializable
data class ListaServicios(val servicios: List<Servicio>)

@Serializable
data class Captcha(@SerialName("captcha_id") val id: String, val pregunta: String, val expira: Long)

@Serializable
data class PedidoLogin(
    val usuario: String,
    val password: String,
    @SerialName("captcha_id") val captchaId: String,
    @SerialName("captcha_respuesta") val captchaRespuesta: String,
)

// Lo que responde el refresh, y lo que se guarda cifrado.
@Serializable
data class Tokens(
    @SerialName("access_token") val access: String,
    @SerialName("refresh_token") val refresh: String,
    @SerialName("expires_in") val expiraEn: Long,
    @SerialName("sesion_expira") val sesionExpira: Long,
)

// El login responde los mismos tokens y además la cuenta: su id y sus roles.
@Serializable
data class Login(
    @SerialName("access_token") val access: String,
    @SerialName("refresh_token") val refresh: String,
    @SerialName("expires_in") val expiraEn: Long,
    @SerialName("sesion_expira") val sesionExpira: Long,
    val usuario: Cuenta,
) {
    val tokens: Tokens
        get() = Tokens(access, refresh, expiraEn, sesionExpira)
}

@Serializable
data class Cuenta(val id: Long, val roles: List<String> = emptyList())

@Serializable
data class PedidoDispositivo(
    @SerialName("device_uid") val uid: String,
    val platform: String,
    val model: String,
    @SerialName("app_version") val appVersion: String,
)

@Serializable
data class Dispositivo(
    val id: Long,
    @SerialName("device_uid") val uid: String,
    @SerialName("is_revoked") val revocado: Boolean = false,
)

@Serializable
data class PedidoRenovar(@SerialName("refresh_token") val refresh: String)

@Serializable
data class Perfil(
    val id: Long,
    val username: String,
    @SerialName("full_name") val nombre: String,
    val email: String? = null,
    @SerialName("last_login_at") val ultimoAcceso: String? = null,
    val roles: List<String> = emptyList(),
    val institucion: String? = null,
    val region: String? = null,
)

@Serializable
data class EnfermedadRemota(val id: Long, val nombre: String)

@Serializable
data class PaginaEnfermedades(val enfermedades: List<EnfermedadRemota>, val paginas: Int = 1)

@Serializable
data class MunicipioRemoto(val id: Long, val nombre: String)

@Serializable
data class ListaMunicipios(val municipios: List<MunicipioRemoto>)

// Los nulos no viajan (json no los escribe): casos los toma como campos que no vinieron.
@Serializable
data class CasoDeLote(
    @SerialName("local_uuid") val localUuid: String,
    @SerialName("disease_id") val enfermedad: Long,
    @SerialName("region_id") val municipio: Long,
    @SerialName("report_date") val fechaReporte: String,
    @SerialName("onset_date") val inicioSintomas: String? = null,
    val age: Int? = null,
    val sex: String? = null,
    @SerialName("test_result") val resultadoPrueba: String? = null,
    val severity: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("form_id") val formulario: Long? = null,
    @SerialName("form_answers") val respuestas: JsonObject? = null,
)

@Serializable
data class PedidoLote(
    @SerialName("batch_id") val lote: String,
    @SerialName("device_id") val dispositivo: Long,
    val cases: List<CasoDeLote>,
)

@Serializable
data class ResultadoDeCaso(
    @SerialName("local_uuid") val localUuid: String,
    val resultado: String,
    @SerialName("case_id") val caseId: Long? = null,
    val codigo: String? = null,
    val errores: List<String> = emptyList(),
)

@Serializable
data class RespuestaLote(
    @SerialName("batch_id") val lote: String,
    val resultados: List<ResultadoDeCaso>,
    val repetido: Boolean = false,
)

@Serializable
data class Evidencia(
    val id: Long,
    @SerialName("case_id") val caso: Long,
    @SerialName("size_bytes") val tamano: Long = 0,
    @SerialName("mime_type") val tipo: String = "image/jpeg",
    // La huella del archivo en el bucket: lo que se baja se compara con ella antes de mostrarlo.
    val sha256: String? = null,
    @SerialName("uploaded_at") val subida: String? = null,
)

@Serializable
data class EvidenciasDeCaso(
    @SerialName("case_id") val caso: Long,
    val evidencias: List<Evidencia> = emptyList(),
)

// D30: un permiso temporal para bajar el archivo directo del bucket; vence en minutos.
@Serializable
data class UrlFirmada(
    val id: Long,
    val url: String,
    @SerialName("expires_at") val vence: String? = null,
)

@Serializable
data class LoteVacuna(
    val id: Long,
    @SerialName("lot_code") val codigo: String,
    @SerialName("manufacturer") val fabricante: String? = null,
    @SerialName("disease_id") val enfermedad: Long,
    @SerialName("disease_name") val nombreEnfermedad: String? = null,
    @SerialName("region_id") val municipio: Long? = null,
    @SerialName("region_name") val nombreMunicipio: String? = null,
    @SerialName("doses_total") val dosisTotales: Int,
    @SerialName("doses_used") val dosisUsadas: Int,
    @SerialName("doses_remaining") val dosisRestantes: Int,
    @SerialName("expires_on") val caducidad: String? = null,
    val vencido: Boolean = false,
)

@Serializable
data class ListaLotesVacuna(val total: Int, val lotes: List<LoteVacuna>)

@Serializable
data class PedidoLoteVacuna(
    @SerialName("lot_code") val codigo: String,
    @SerialName("disease_id") val enfermedad: Long,
    @SerialName("doses_total") val dosisTotales: Int,
    @SerialName("manufacturer") val fabricante: String? = null,
    @SerialName("region_id") val municipio: Long? = null,
    @SerialName("expires_on") val caducidad: String? = null,
)

@Serializable
data class PedidoDosis(val doses: Int)

// El payload (los ids para llegar al recurso) no se usa en la app: se ignora.
@Serializable
data class Aviso(
    val id: Long,
    @SerialName("type") val tipo: String,
    @SerialName("title") val titulo: String,
    @SerialName("body") val cuerpo: String? = null,
    @SerialName("read_at") val leidoEn: String? = null,
    @SerialName("created_at") val creadoEn: String,
) {
    val leido: Boolean
        get() = leidoEn != null
}

@Serializable
data class ListaAvisos(
    val total: Int,
    @SerialName("no_leidas") val noLeidas: Int,
    @SerialName("notificaciones") val avisos: List<Aviso>,
)

// El formulario de una enfermedad (D48): los campos que suma a los fijos del caso.
@Serializable
data class OpcionDeCampo(val valor: String, val etiqueta: String)

@Serializable
data class CampoDeFormulario(
    val clave: String,
    val etiqueta: String,
    val tipo: String,
    val obligatorio: Boolean = false,
    val minimo: Double? = null,
    val maximo: Double? = null,
    @SerialName("max_largo") val largoMaximo: Int? = null,
    val opciones: List<OpcionDeCampo> = emptyList(),
    val ayuda: String? = null,
)

@Serializable
data class Formulario(
    val id: Long,
    @SerialName("disease_id") val enfermedad: Long,
    val version: Int,
    @SerialName("title") val titulo: String,
    @SerialName("fields") val campos: List<CampoDeFormulario>,
)

@Serializable
data class ListaFormularios(val formularios: List<Formulario>)

// Un caso como lo tiene el servidor (casos), para el seguimiento (D47) y los incompletos (D49).
@Serializable
data class CasoRemoto(
    val id: Long,
    @SerialName("reported_by") val capturadoPor: Long? = null,
    @SerialName("disease_id") val enfermedad: Long,
    @SerialName("enfermedad") val nombreEnfermedad: String? = null,
    @SerialName("region_id") val municipio: Long,
    @SerialName("municipio") val nombreMunicipio: String? = null,
    val age: Int? = null,
    val sex: String? = null,
    @SerialName("onset_date") val inicioSintomas: String? = null,
    @SerialName("report_date") val fechaReporte: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("test_result") val resultadoPrueba: String? = null,
    val severity: String? = null,
    val status: String,
    val version: Int = 1,
    @SerialName("status_reason") val motivo: String? = null,
    val faltantes: List<String> = emptyList(),
)

@Serializable
data class ListaCasosRemotos(val casos: List<CasoRemoto>, val total: Int = 0)

@Serializable
data class CambioDeCaso(
    val version: Int,
    val action: String,
    @SerialName("changed_at") val cuando: String,
    @SerialName("status_before") val estadoAntes: String? = null,
    @SerialName("status_after") val estadoDespues: String? = null,
    @SerialName("changes") val cambios: JsonObject = JsonObject(emptyMap()),
    val reason: String? = null,
)

@Serializable
data class HistorialDeCaso(val cambios: List<CambioDeCaso> = emptyList())

// Una fila de la consulta por zona (zonas): casos e incidencia por 100 mil en el periodo.
@Serializable
data class Zona(
    val id: Long,
    val zona: String,
    val casos: Int,
    val incidencia: Double,
    val graves: Int = 0,
    val estado: String,
)

@Serializable
data class ListaZonas(val zonas: List<Zona>, val total: Int = 0)

// RFC 7807, como lo arma epidemia_comun.errores.
@Serializable
data class Problema(val status: Int = 0, val detail: String = "", val codigo: String = "")
