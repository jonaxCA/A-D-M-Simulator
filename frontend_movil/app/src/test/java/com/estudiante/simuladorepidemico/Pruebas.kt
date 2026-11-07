package com.estudiante.simuladorepidemico

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import com.estudiante.simuladorepidemico.red.Tokens
import com.estudiante.simuladorepidemico.sesion.Cifrador
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import java.io.File
import java.nio.file.Files
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicInteger

// Reversible y sin Keystore, que no existe en las pruebas locales.
class CifradorDePrueba : Cifrador {
    @Volatile
    var sinLlave = false

    override fun cifrar(texto: String) = "cifrado:" + texto.reversed()

    override fun descifrar(cifrado: String): String {
        check(!sinLlave) { "La llave ya no existe." }
        return cifrado.removePrefix("cifrado:").reversed()
    }
}

fun datosTemporales(): DataStore<Preferences> {
    val carpeta = Files.createTempDirectory("sesion").toFile()
    return PreferenceDataStoreFactory.create(scope = CoroutineScope(Dispatchers.IO + SupervisorJob())) {
        File(carpeta, "sesion.preferences_pb")
    }
}

fun tokens(access: String, refresh: String) = Tokens(access, refresh, 1200, 1_800_000_000)

// Los servicios que usan red y sesion, en un solo MockWebServer que el directorio anuncia.
class ServidorFalso : Dispatcher() {
    private val servidor = MockWebServer()
    private var apagado = false
    val pedidos = CopyOnWriteArrayList<RecordedRequest>()
    val renovaciones = AtomicInteger()

    @Volatile var accessValido = "nuevo"
    @Volatile var codigo401 = "TOKEN_EXPIRADO"
    @Volatile var antesDel401: () -> Unit = {}
    @Volatile var renovar: MockResponse = respuesta(200, cuerpoTokens("nuevo", "r2"))
    @Volatile var login: MockResponse = respuesta(200, cuerpoTokens("a1", "r1"))

    init {
        servidor.dispatcher = this
        servidor.start()
    }

    val url: String = servidor.url("/").toString()

    fun apagar() {
        if (!apagado) servidor.shutdown()
        apagado = true
    }

    fun pedidosA(ruta: String) = pedidos.filter { it.path?.substringBefore('?') == ruta }

    override fun dispatch(request: RecordedRequest): MockResponse {
        pedidos += request
        return when (request.path?.substringBefore('?')) {
            "/api/v1/services" -> respuesta(200, directorio())
            "/api/v1/auth/captcha" -> respuesta(200, """{"captcha_id":"c1","pregunta":"3 + 5","expira":1}""")
            "/api/v1/auth/login" -> login
            "/api/v1/sessions/refresh" -> {
                renovaciones.incrementAndGet()
                renovar
            }
            "/api/v1/sessions/logout" -> respuesta(200, """{"cerrada":true}""")
            "/api/v1/users/me" ->
                if (request.getHeader("Authorization") == "Bearer $accessValido") {
                    respuesta(200, PERFIL)
                } else {
                    antesDel401()
                    problema(401, codigo401)
                }
            else -> MockResponse().setResponseCode(404)
        }
    }

    private fun directorio(): String {
        val base = url.trimEnd('/')
        return listOf("auth", "sesiones", "usuarios").joinToString(",", "{\"servicios\":[", "]}") {
            "{\"nombre\":\"$it\",\"dominio\":\"prueba\",\"puerto\":1,\"url\":\"$base\"}"
        }
    }

    companion object {
        const val PERFIL = """{"id":12,"username":"capturista1","email":"c@ejemplo.mx","full_name":"Carla Captura","is_active":true,"last_login_at":null,"created_at":"2026-09-01T10:00:00-06:00","role_id":4,"roles":["CAPTURISTA"]}"""

        fun respuesta(estado: Int, cuerpo: String): MockResponse = MockResponse()
            .setResponseCode(estado).setHeader("Content-Type", "application/json").setBody(cuerpo)

        fun problema(estado: Int, codigo: String): MockResponse = MockResponse()
            .setResponseCode(estado).setHeader("Content-Type", "application/problem+json")
            .setBody("{\"type\":\"about:blank\",\"title\":\"Error\",\"status\":$estado,\"detail\":\"Detalle de $codigo.\",\"codigo\":\"$codigo\",\"instance\":\"/\"}")

        fun cuerpoTokens(access: String, refresh: String) =
            "{\"access_token\":\"$access\",\"refresh_token\":\"$refresh\",\"token_type\":\"Bearer\",\"expires_in\":1200,\"sesion_expira\":1800000000}"
    }
}
