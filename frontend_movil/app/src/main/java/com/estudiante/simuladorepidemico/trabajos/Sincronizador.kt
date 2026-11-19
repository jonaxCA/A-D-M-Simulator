package com.estudiante.simuladorepidemico.trabajos

import com.estudiante.simuladorepidemico.local.CasoLocal
import com.estudiante.simuladorepidemico.local.CasosDao
import com.estudiante.simuladorepidemico.local.Fotos
import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.red.CasoDeLote
import com.estudiante.simuladorepidemico.red.PedidoLote
import com.estudiante.simuladorepidemico.red.mensajeDeError
import com.estudiante.simuladorepidemico.sesion.Sesion
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.asRequestBody
import retrofit2.HttpException
import java.io.IOException
import java.util.UUID

enum class Envio {
    // No queda nada por mandar.
    LISTO,

    // Falló la red o el servidor: el mismo lote se vuelve a intentar más tarde.
    REINTENTAR,

    // No hay sesión, se perdió o el teléfono está revocado: se manda cuando la cuenta vuelva a entrar.
    SIN_SESION,
}

// Manda los casos pendientes de la cuenta de la sesión a sincronizacion, en lotes de hasta 100
// (README, sección 5), y después sube a evidencias las fotos de los que ya tienen case_id
// (sección 7). Un lote sin respuesta se reenvía igual, y una foto otra vez: el servidor no duplica.
class Sincronizador(
    private val sesion: Sesion,
    private val apis: Apis,
    private val casos: CasosDao,
    private val fotos: Fotos,
    private val nuevoLote: () -> String = { UUID.randomUUID().toString() },
) {
    private val candado = Mutex()

    suspend fun enviar(): Envio = candado.withLock {
        val cuenta = sesion.cuenta() ?: return Envio.SIN_SESION
        val lotes = enviarLotes(cuenta)
        if (lotes == Envio.SIN_SESION) return Envio.SIN_SESION
        // Aunque un lote falle, se suben las fotos de los casos que ya estaban en el servidor.
        val subidas = subirFotos(cuenta)
        if (lotes == Envio.REINTENTAR && subidas == Envio.LISTO) Envio.REINTENTAR else subidas
    }

    private suspend fun subirFotos(cuenta: Long): Envio {
        for (foto in casos.fotosPorSubir(cuenta)) {
            val archivo = fotos.archivo(foto.id)
            if (!archivo.exists()) {
                casos.marcarFotoRechazada(foto.id, "El archivo de la foto ya no está en el teléfono.")
                continue
            }
            try {
                val evidencia = apis.evidencias().subir(foto.caseId, archivo.asRequestBody(JPEG))
                casos.marcarFotoSubida(foto.id, evidencia.id)
                // Ya está en el servidor: del teléfono se borra.
                fotos.borrar(listOf(foto.id))
            } catch (e: IOException) {
                return Envio.REINTENTAR
            } catch (e: HttpException) {
                when (e.code()) {
                    401 -> return Envio.SIN_SESION
                    // Otro dueño, caso inexistente o archivo que evidencias no acepta: reintentar
                    // daría lo mismo. La foto no se va a subir, así que tampoco se queda.
                    403, 404, 413, 422 -> {
                        casos.marcarFotoRechazada(foto.id, mensajeDeError(e))
                        fotos.borrar(listOf(foto.id))
                    }
                    else -> return Envio.REINTENTAR
                }
            }
        }
        return Envio.LISTO
    }

    private suspend fun enviarLotes(cuenta: Long): Envio {
        for (vuelta in 1..MAXIMO_DE_LOTES) {
            val lote = casos.siguienteLote(cuenta, nuevoLote()) ?: return Envio.LISTO
            // Sin el teléfono registrado el caso entraría sin ligarse a él: primero se registra.
            val dispositivo = try {
                sesion.dispositivo() ?: sesion.registrarTelefono()
            } catch (e: HttpException) {
                // 409: revocado, y registrarTelefono ya cerró la sesión.
                return if (e.code() == 409 || e.code() == 401) Envio.SIN_SESION else Envio.REINTENTAR
            } catch (e: IOException) {
                return Envio.REINTENTAR
            }
            val respuesta = try {
                apis.sincronizacion().enviar(PedidoLote(lote.id, dispositivo, lote.casos.map(::paraLote)))
            } catch (e: IOException) {
                return Envio.REINTENTAR
            } catch (e: HttpException) {
                when (e.code()) {
                    // El Renovador ya intentó renovar: la sesión no sirve.
                    401 -> return Envio.SIN_SESION
                    // El rol no puede registrar casos, o el lote no pasó la revisión: reenviarlo
                    // daría lo mismo.
                    403, 422 -> {
                        val motivo = mensajeDeError(e)
                        casos.aplicar(lote.id, emptyMap(), lote.casos.associate { it.localUuid to motivo })
                        continue
                    }
                    // 409: otra petición está procesando este lote. 503: casos no respondió.
                    else -> return Envio.REINTENTAR
                }
            }
            val enviados = respuesta.resultados.filter { it.resultado == "creado" || it.resultado == "duplicado" }
                .associate { it.localUuid to it.caseId }
            val rechazados = respuesta.resultados
                .filter { it.resultado == "rechazado" && it.codigo != REVOCADO }
                .associate { it.localUuid to (it.errores.firstOrNull() ?: "El servidor rechazó el caso.") }
            casos.aplicar(lote.id, enviados, rechazados)
            // Teléfono revocado: los casos no tienen nada malo y vuelven a pendientes. Se cierra la
            // sesión para que la persona entre con su contraseña y registre el teléfono de nuevo.
            if (respuesta.resultados.any { it.codigo == REVOCADO }) {
                sesion.cerrar()
                return Envio.SIN_SESION
            }
        }
        return Envio.REINTENTAR
    }

    private fun paraLote(caso: CasoLocal) = CasoDeLote(
        localUuid = caso.localUuid,
        enfermedad = caso.enfermedad,
        municipio = caso.municipio,
        fechaReporte = caso.fechaReporte,
        inicioSintomas = caso.inicioSintomas,
        age = caso.edad,
        sex = caso.sexo,
        resultadoPrueba = caso.resultadoPrueba,
        severity = caso.severidad,
        latitude = caso.latitud,
        longitude = caso.longitud,
    )

    private companion object {
        const val REVOCADO = "CONFLICTO"
        val JPEG = "image/jpeg".toMediaType()

        // Mil casos por corrida; si quedan más, la siguiente sigue.
        const val MAXIMO_DE_LOTES = 10
    }
}
