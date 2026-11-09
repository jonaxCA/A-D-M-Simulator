package com.estudiante.simuladorepidemico.red

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

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

// El login responde los mismos tokens y además la cuenta, de la que basta el id.
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
data class Cuenta(val id: Long)

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

// RFC 7807, como lo arma epidemia_comun.errores.
@Serializable
data class Problema(val status: Int = 0, val detail: String = "", val codigo: String = "")
