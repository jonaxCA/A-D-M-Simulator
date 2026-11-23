package com.estudiante.simuladorepidemico.red

import com.estudiante.simuladorepidemico.red.api.AuthApi
import com.estudiante.simuladorepidemico.red.api.CasosApi
import com.estudiante.simuladorepidemico.red.api.DispositivosApi
import com.estudiante.simuladorepidemico.red.api.EnfermedadesApi
import com.estudiante.simuladorepidemico.red.api.EvidenciasApi
import com.estudiante.simuladorepidemico.red.api.NotificacionesApi
import com.estudiante.simuladorepidemico.red.api.RegionesApi
import com.estudiante.simuladorepidemico.red.api.SesionesApi
import com.estudiante.simuladorepidemico.red.api.SincronizacionApi
import com.estudiante.simuladorepidemico.red.api.UsuariosApi
import com.estudiante.simuladorepidemico.red.api.VacunasApi
import com.estudiante.simuladorepidemico.red.api.ZonasApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okio.Buffer
import java.io.IOException
import java.util.concurrent.ConcurrentHashMap

const val MAXIMO_A_BAJAR = 20L * 1_048_576

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
    suspend fun vacunas(): VacunasApi = crear("vacunas", conToken)
    suspend fun notificaciones(): NotificacionesApi = crear("notificaciones", conToken)
    suspend fun casos(): CasosApi = crear("casos", conToken)
    suspend fun zonas(): ZonasApi = crear("zonas", conToken)
    suspend fun enfermedades(): EnfermedadesApi = crear("enfermedades", sinToken)
    suspend fun regiones(): RegionesApi = crear("regiones", sinToken)

    // Un archivo de una URL firmada de evidencias (D30). Va directo al bucket con el cliente sin
    // token: el de la sesión no debe salir hacia Google. Más de `maximo` bytes (20 MB, el tope de
    // evidencias) no se baja.
    suspend fun bajarFirmada(url: String, maximo: Long = MAXIMO_A_BAJAR): ByteArray = withContext(Dispatchers.IO) {
        sinToken.newCall(Request.Builder().url(url).build()).execute().use { respuesta ->
            if (!respuesta.isSuccessful) throw IOException("El bucket respondió ${respuesta.code}.")
            val fuente = respuesta.body.source()
            val leido = Buffer()
            while (fuente.read(leido, 8_192) != -1L) {
                if (leido.size > maximo) throw IOException("El archivo pasa de ${maximo / 1_048_576} MB.")
            }
            leido.readByteArray()
        }
    }

    private suspend inline fun <reified T : Any> crear(servicio: String, cliente: OkHttpClient): T {
        creadas[servicio]?.let { return it as T }
        val url = withContext(Dispatchers.IO) { directorio.url(servicio) }
        return retrofit(url, cliente).create(T::class.java).also { creadas[servicio] = it }
    }
}
