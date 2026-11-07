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

// El login y el refresh responden lo mismo; el login trae además la cuenta, que se ignora.
@Serializable
data class Tokens(
    @SerialName("access_token") val access: String,
    @SerialName("refresh_token") val refresh: String,
    @SerialName("expires_in") val expiraEn: Long,
    @SerialName("sesion_expira") val sesionExpira: Long,
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

// RFC 7807, como lo arma epidemia_comun.errores.
@Serializable
data class Problema(val status: Int = 0, val detail: String = "", val codigo: String = "")
