package com.estudiante.simuladorepidemico

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import com.estudiante.simuladorepidemico.local.Fotos
import com.estudiante.simuladorepidemico.red.Tokens
import com.estudiante.simuladorepidemico.red.json
import com.estudiante.simuladorepidemico.sesion.Cifrador
import com.estudiante.simuladorepidemico.sesion.DescripcionTelefono
import com.estudiante.simuladorepidemico.ubicacion.Lectura
import com.estudiante.simuladorepidemico.ubicacion.Ubicador
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import okhttp3.mockwebserver.SocketPolicy
import java.io.File
import java.nio.file.Files
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong

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

val telefonoDePrueba = DescripcionTelefono("Pixel de prueba", "0.1.0")

fun contenedorDePrueba(
    servidor: ServidorFalso,
    casos: CasosDaoFalso = CasosDaoFalso(),
    catalogo: CatalogoDaoFalso = CatalogoDaoFalso(),
    ubicador: Ubicador = Ubicador { Lectura.SinSenal },
    fotos: Fotos = fotosDePrueba(),
    programarAvisos: () -> Unit = {},
    programarEnvio: () -> Unit = {},
) = Contenedor(
    datosTemporales(), CifradorDePrueba(), servidor.url, telefonoDePrueba, casos, catalogo, programarEnvio, ubicador, fotos,
    programarAvisos,
)

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
    @Volatile var login: MockResponse = respuesta(200, cuerpoLogin("a1", "r1", cuenta = 12))

    // dispositivos: los uid registrados con su id, como el servicio. Con `dispositivos` puesto,
    // responde eso en lugar de registrar.
    val registrados = ConcurrentHashMap<String, Long>()
    val revocados: MutableSet<String> = ConcurrentHashMap.newKeySet()
    @Volatile var dispositivos: MockResponse? = null
    private val siguienteId = AtomicLong(3)

    // sincronizacion, como el servicio: crea una vez por local_uuid, rechaza el municipio 999 y
    // guarda el resultado de cada batch_id. Con `telefonoRevocado`, lo nuevo sale CONFLICTO; con
    // `lote` puesto, responde eso.
    val casosCreados = ConcurrentHashMap<String, Long>()
    private val siguienteCaso = AtomicLong(41)
    private val lotesGuardados = ConcurrentHashMap<String, String>()
    @Volatile var telefonoRevocado = false
    @Volatile var lote: MockResponse? = null

    // Los catálogos: `enfermedades` se pagina como el servicio.
    @Volatile var enfermedades: List<Pair<Long, String>> = listOf(1L to "Dengue", 2L to "Influenza")
    @Volatile var municipios: List<Pair<Long, String>> = listOf(10L to "Monterrey", 11L to "Apodaca")

    // evidencias: responde 201 con un id nuevo, o `evidencia` si está puesto.
    @Volatile var evidencia: MockResponse? = null
    private val siguienteEvidencia = AtomicLong(12)

    // vacunas, como el servicio: un lote por código; aplicar nunca pasa de las que quedan ni a uno
    // caducado. Con `cortarDosis`, aplica y corta la conexión sin responder.
    class LoteFalso(val id: Long, val codigo: String, val total: Int, var usadas: Int = 0, val vencido: Boolean = false)

    val lotesVacuna = ConcurrentHashMap<String, LoteFalso>()
    private val siguienteLote = AtomicLong(5)
    @Volatile var cortarDosis = false

    fun nuevoLote(codigo: String, total: Int, usadas: Int = 0, vencido: Boolean = false) =
        LoteFalso(siguienteLote.getAndIncrement(), codigo, total, usadas, vencido).also { lotesVacuna[codigo] = it }

    private fun json(lote: LoteFalso) =
        """{"id":${lote.id},"lot_code":"${lote.codigo}","manufacturer":"Pfizer","disease_id":1,"disease_name":"Influenza A","region_id":null,"region_name":null,"doses_total":${lote.total},"doses_used":${lote.usadas},"doses_remaining":${lote.total - lote.usadas},"expires_on":"2027-03-31","vencido":${lote.vencido}}"""

    private fun vacunas(pedido: RecordedRequest, ruta: String): MockResponse? {
        fun porId(id: String) = lotesVacuna.values.firstOrNull { it.id == id.toLong() }
        DOSIS.matchEntire(ruta)?.let { m ->
            val lote = porId(m.groupValues[1]) ?: return problema(404, "NO_ENCONTRADO")
            val dosis = json.parseToJsonElement(pedido.body.clone().readUtf8()).jsonObject["doses"]!!.jsonPrimitive.int
            synchronized(lote) {
                if (lote.vencido || lote.usadas + dosis > lote.total) return problema(409, "CONFLICTO")
                lote.usadas += dosis
            }
            return if (cortarDosis) MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST)
            else respuesta(200, json(lote))
        }
        UN_LOTE.matchEntire(ruta)?.let { m ->
            return porId(m.groupValues[1])?.let { respuesta(200, json(it)) } ?: problema(404, "NO_ENCONTRADO")
        }
        if (ruta != "/api/v1/vaccine-lots") return null
        if (pedido.method == "GET") {
            val codigo = pedido.requestUrl!!.queryParameter("lot_code")
            val lista = lotesVacuna.values.filter { codigo == null || it.codigo == codigo }
            return respuesta(200, lista.joinToString(",", "{\"total\":${lista.size},\"lotes\":[", "]}") { json(it) })
        }
        val cuerpo = json.parseToJsonElement(pedido.body.clone().readUtf8()).jsonObject
        val codigo = cuerpo["lot_code"]!!.jsonPrimitive.content
        val total = cuerpo["doses_total"]!!.jsonPrimitive.int
        lotesVacuna[codigo]?.let { ya -> return if (ya.total == total) respuesta(200, json(ya)) else problema(409, "CONFLICTO") }
        return respuesta(201, json(nuevoLote(codigo, total)))
    }

    // notificaciones: los avisos de la cuenta, del más nuevo al más viejo.
    class AvisoFalso(val id: Long, val titulo: String, var leido: Boolean = false)

    val avisosFalsos = CopyOnWriteArrayList<AvisoFalso>()

    fun nuevoAviso(id: Long, titulo: String, leido: Boolean = false) = AvisoFalso(id, titulo, leido).also { avisosFalsos += it }

    private fun json(aviso: AvisoFalso) =
        """{"id":${aviso.id},"user_id":12,"type":"RUN_FINISHED","title":"${aviso.titulo}","body":"Cuerpo de ${aviso.id}.","payload":{"run_id":42},"read_at":${if (aviso.leido) "\"2026-11-07T15:05:00+00:00\"" else "null"},"created_at":"2026-11-07T15:02:00+00:00"}"""

    private fun notificaciones(pedido: RecordedRequest, ruta: String): MockResponse? {
        LEIDO.matchEntire(ruta)?.let { m ->
            val aviso = avisosFalsos.firstOrNull { it.id == m.groupValues[1].toLong() } ?: return problema(404, "NO_ENCONTRADO")
            aviso.leido = true
            return respuesta(200, json(aviso))
        }
        if (ruta != "/api/v1/notifications") return null
        val soloNoLeidos = pedido.requestUrl!!.queryParameter("unread") == "true"
        val limite = pedido.requestUrl!!.queryParameter("limit")?.toInt() ?: 50
        val lista = avisosFalsos.filter { !soloNoLeidos || !it.leido }.sortedByDescending { it.id }
        return respuesta(
            200,
            lista.take(limite).joinToString(
                ",", "{\"total\":${lista.size},\"no_leidas\":${avisosFalsos.count { !it.leido }},\"notificaciones\":[", "]}",
            ) { json(it) },
        )
    }

    // Las subidas a evidencias: el case_id de la ruta y el pedido.
    fun subidas(): List<Pair<Long, RecordedRequest>> = pedidos.mapNotNull { pedido ->
        SUBIDA.matchEntire(pedido.path.orEmpty().substringBefore('?'))?.let { it.groupValues[1].toLong() to pedido }
    }

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

    // Los device_uid que llegaron a dispositivos, en orden.
    fun uidsEnviados() = pedidosA("/api/v1/devices").map(::uid)

    private fun uid(pedido: RecordedRequest): String =
        json.parseToJsonElement(pedido.body.clone().readUtf8()).jsonObject["device_uid"]!!.jsonPrimitive.content

    private fun registrar(pedido: RecordedRequest): MockResponse {
        val uid = uid(pedido)
        if (uid in revocados) return problema(409, "CONFLICTO")
        var nuevo = false
        val id = registrados.computeIfAbsent(uid) { nuevo = true; siguienteId.getAndIncrement() }
        return respuesta(
            if (nuevo) 201 else 200,
            """{"id":$id,"user_id":12,"device_uid":"$uid","platform":"android","model":"Pixel de prueba","is_revoked":false,"has_push_token":false}""",
        )
    }

    // Los lotes que llegaron a sincronizacion, ya leídos.
    fun lotesEnviados(): List<JsonObject> =
        pedidosA("/api/v1/sync/cases").map { json.parseToJsonElement(it.body.clone().readUtf8()).jsonObject }

    private fun sincronizar(pedido: RecordedRequest): MockResponse {
        lote?.let { return it }
        val cuerpo = json.parseToJsonElement(pedido.body.clone().readUtf8()).jsonObject
        val id = cuerpo["batch_id"]!!.jsonPrimitive.content
        lotesGuardados[id]?.let { return respuesta(200, it.replace("\"repetido\":false", "\"repetido\":true")) }
        val resultados = cuerpo["cases"]!!.jsonArray.mapIndexed { indice, elemento ->
            val caso = elemento.jsonObject
            val uuid = caso["local_uuid"]!!.jsonPrimitive.content
            fun rechazado(codigo: String, error: String) =
                """{"indice":$indice,"local_uuid":"$uuid","resultado":"rechazado","case_id":null,"codigo":"$codigo","errores":["$error"]}"""
            when {
                telefonoRevocado && !casosCreados.containsKey(uuid) ->
                    rechazado("CONFLICTO", "El dispositivo está revocado: ya no puede capturar ni sincronizar casos.")
                caso["region_id"]!!.jsonPrimitive.long == 999L ->
                    rechazado("DATOS_INVALIDOS", "Ese municipio no está en el catálogo de Nuevo León.")
                else -> {
                    var nuevo = false
                    val caseId = casosCreados.computeIfAbsent(uuid) { nuevo = true; siguienteCaso.getAndIncrement() }
                    val resultado = if (nuevo) "creado" else "duplicado"
                    """{"indice":$indice,"local_uuid":"$uuid","resultado":"$resultado","case_id":$caseId,"codigo":null,"errores":[]}"""
                }
            }
        }
        val texto = """{"batch_id":"$id","device_id":${cuerpo["device_id"]},"resultados":[${resultados.joinToString(",")}],"repetido":false}"""
        lotesGuardados[id] = texto
        return respuesta(200, texto)
    }

    private fun paginaEnfermedades(pedido: RecordedRequest): MockResponse {
        val pagina = pedido.requestUrl!!.queryParameter("page")!!.toInt()
        val tamano = pedido.requestUrl!!.queryParameter("size")!!.toInt()
        val lista = enfermedades.drop((pagina - 1) * tamano).take(tamano)
        val paginas = (enfermedades.size + tamano - 1) / tamano
        return respuesta(200, lista.joinToString(",", "{\"enfermedades\":[", "],\"total\":${enfermedades.size},\"pagina\":$pagina,\"paginas\":$paginas}") {
            "{\"id\":${it.first},\"code\":\"E${it.first}\",\"nombre\":\"${it.second}\",\"activa\":true}"
        })
    }

    override fun dispatch(request: RecordedRequest): MockResponse {
        pedidos += request
        vacunas(request, request.path.orEmpty().substringBefore('?'))?.let { return it }
        notificaciones(request, request.path.orEmpty().substringBefore('?'))?.let { return it }
        SUBIDA.matchEntire(request.path.orEmpty().substringBefore('?'))?.let { ruta ->
            return evidencia ?: respuesta(
                201,
                """{"id":${siguienteEvidencia.getAndIncrement()},"case_id":${ruta.groupValues[1]},"mime_type":"image/jpeg","size_bytes":${request.bodySize}}""",
            )
        }
        return when (request.path?.substringBefore('?')) {
            "/api/v1/sync/cases" -> sincronizar(request)
            "/api/v1/diseases" -> paginaEnfermedades(request)
            "/api/v1/regions" -> respuesta(200, municipios.joinToString(",", "{\"municipios\":[", "],\"total\":${municipios.size}}") {
                "{\"id\":${it.first},\"code\":\"M${it.first}\",\"nombre\":\"${it.second}\",\"poblacion\":1}"
            })
            "/api/v1/services" -> respuesta(200, directorio())
            "/api/v1/auth/captcha" -> respuesta(200, """{"captcha_id":"c1","pregunta":"3 + 5","expira":1}""")
            "/api/v1/auth/login" -> login
            "/api/v1/sessions/refresh" -> {
                renovaciones.incrementAndGet()
                renovar
            }
            "/api/v1/sessions/logout" -> respuesta(200, """{"cerrada":true}""")
            "/api/v1/devices" -> dispositivos ?: registrar(request)
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
        return listOf(
            "auth", "sesiones", "usuarios", "dispositivos", "sincronizacion", "enfermedades", "regiones", "evidencias",
            "vacunas", "notificaciones",
        ).joinToString(",", "{\"servicios\":[", "]}") {
            "{\"nombre\":\"$it\",\"dominio\":\"prueba\",\"puerto\":1,\"url\":\"$base\"}"
        }
    }

    companion object {
        private val SUBIDA = Regex("/api/v1/cases/(\\d+)/attachments")
        private val UN_LOTE = Regex("/api/v1/vaccine-lots/(\\d+)")
        private val DOSIS = Regex("/api/v1/vaccine-lots/(\\d+)/doses")
        private val LEIDO = Regex("/api/v1/notifications/(\\d+)/read")

        const val PERFIL = """{"id":12,"username":"capturista1","email":"c@ejemplo.mx","full_name":"Carla Captura","is_active":true,"last_login_at":null,"created_at":"2026-09-01T10:00:00-06:00","role_id":4,"roles":["CAPTURISTA"]}"""

        fun respuesta(estado: Int, cuerpo: String): MockResponse = MockResponse()
            .setResponseCode(estado).setHeader("Content-Type", "application/json").setBody(cuerpo)

        fun problema(estado: Int, codigo: String): MockResponse = MockResponse()
            .setResponseCode(estado).setHeader("Content-Type", "application/problem+json")
            .setBody("{\"type\":\"about:blank\",\"title\":\"Error\",\"status\":$estado,\"detail\":\"Detalle de $codigo.\",\"codigo\":\"$codigo\",\"instance\":\"/\"}")

        fun cuerpoTokens(access: String, refresh: String) =
            "{\"access_token\":\"$access\",\"refresh_token\":\"$refresh\",\"token_type\":\"Bearer\",\"expires_in\":1200,\"sesion_expira\":1800000000}"

        fun cuerpoLogin(access: String, refresh: String, cuenta: Long) =
            cuerpoTokens(access, refresh).dropLast(1) +
                ",\"usuario\":{\"id\":$cuenta,\"username\":\"capturista$cuenta\",\"roles\":[\"CAPTURISTA\"]}}"
    }
}
