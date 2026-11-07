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

// RFC 7807, como lo arma epidemia_comun.errores.
@Serializable
data class Problema(val status: Int = 0, val detail: String = "", val codigo: String = "")
