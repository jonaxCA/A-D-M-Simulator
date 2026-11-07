package com.estudiante.simuladorepidemico.red

import com.estudiante.simuladorepidemico.red.api.AuthApi
import com.estudiante.simuladorepidemico.red.api.DispositivosApi
import com.estudiante.simuladorepidemico.red.api.EnfermedadesApi
import com.estudiante.simuladorepidemico.red.api.EvidenciasApi
import com.estudiante.simuladorepidemico.red.api.RegionesApi
import com.estudiante.simuladorepidemico.red.api.SesionesApi
import com.estudiante.simuladorepidemico.red.api.SincronizacionApi
import com.estudiante.simuladorepidemico.red.api.UsuariosApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import java.util.concurrent.ConcurrentHashMap

class Apis(
    private val directorio: Directorio,
    private val conToken: OkHttpClient,
    private val sinToken: OkHttpClient,
) {
    private val creadas = ConcurrentHashMap<String, Any>()

    suspend fun auth(): AuthApi = crear("auth", sinToken)
    suspend fun sesiones(): SesionesApi = crear("sesiones", conToken)
    suspend fun usuarios(): UsuariosApi = crear("usuarios", conToken)
    suspend fun dispositivos(): DispositivosApi = crear("dispositivos", conToken)
    suspend fun sincronizacion(): SincronizacionApi = crear("sincronizacion", conToken)
    suspend fun evidencias(): EvidenciasApi = crear("evidencias", conToken)
    suspend fun enfermedades(): EnfermedadesApi = crear("enfermedades", sinToken)
    suspend fun regiones(): RegionesApi = crear("regiones", sinToken)

    private suspend inline fun <reified T : Any> crear(servicio: String, cliente: OkHttpClient): T {
        creadas[servicio]?.let { return it as T }
        val url = withContext(Dispatchers.IO) { directorio.url(servicio) }
        return retrofit(url, cliente).create(T::class.java).also { creadas[servicio] = it }
    }
}
