package com.estudiante.simuladorepidemico.red

import com.estudiante.simuladorepidemico.red.api.SesionesApi
import com.estudiante.simuladorepidemico.sesion.AlmacenSesion
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import java.io.IOException

// Renueva el access con una sola renovación a la vez (README, sección 4): reusar un refresh
// cierra la sesión completa. `sesiones` debe usar un cliente sin este Authenticator.
class Renovador(
    private val almacen: AlmacenSesion,
    private val sesiones: () -> SesionesApi,
) : Authenticator {
    private val candado = Any()

    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.priorResponse != null) return null
        val usado = response.request.header("Authorization")?.removePrefix("Bearer ") ?: return null
        val codigo = problema(response)?.codigo
        synchronized(candado) {
            val actuales = runBlocking { almacen.tokens() } ?: return null
            // Otra petición ya renovó, o se inició sesión de nuevo: basta reintentar.
            if (actuales.access != usado) return conAccess(response.request, actuales.access)
            when (codigo) {
                "TOKEN_EXPIRADO" -> Unit
                "TOKEN_INVALIDO", "TOKEN_REVOCADO" -> {
                    runBlocking { almacen.borrar() }
                    return null
                }
                else -> return null
            }
            val renovacion = try {
                sesiones().renovar(PedidoRenovar(actuales.refresh)).execute()
            } catch (e: IOException) {
                return null
            }
            val nuevos = renovacion.body()
            if (!renovacion.isSuccessful || nuevos == null) {
                // 401: el refresh ya no sirve y hay que volver a iniciar sesión. 503 u otro:
                // la sesión sigue, solo falló esta vez.
                if (renovacion.code() == 401) runBlocking { almacen.borrar() }
                return null
            }
            // Se guarda antes de usarlo: si la app se cierra aquí, no queda el refresh viejo.
            runBlocking { almacen.guardar(nuevos) }
            return conAccess(response.request, nuevos.access)
        }
    }

    private fun conAccess(pedido: Request, access: String) =
        pedido.newBuilder().header("Authorization", "Bearer $access").build()
}
