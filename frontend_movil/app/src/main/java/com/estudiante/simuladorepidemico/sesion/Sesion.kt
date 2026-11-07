package com.estudiante.simuladorepidemico.sesion

import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.red.Captcha
import com.estudiante.simuladorepidemico.red.PedidoLogin
import com.estudiante.simuladorepidemico.red.Perfil
import kotlinx.coroutines.flow.Flow
import java.io.IOException

// Los errores del servidor llegan como HttpException; problema() saca su codigo y detail.
class Sesion(private val apis: Apis, private val almacen: AlmacenSesion) {
    val activa: Flow<Boolean> = almacen.activa

    suspend fun captcha(): Captcha = apis.auth().captcha()

    suspend fun iniciar(usuario: String, password: String, captcha: Captcha, respuesta: String) {
        almacen.guardar(apis.auth().iniciar(PedidoLogin(usuario, password, captcha.id, respuesta)))
    }

    suspend fun perfil(): Perfil = apis.usuarios().perfil()

    // Época Unix. La sesión dura 8 horas desde el login y renovar el access no la alarga.
    suspend fun vence(): Long? = almacen.tokens()?.sesionExpira

    // Lo guardado se borra aunque el servidor no conteste: salir siempre funciona.
    suspend fun cerrar() {
        try {
            apis.sesiones().cerrar()
        } catch (e: IOException) {
            // Sin red: la sesión del servidor vence sola.
        } finally {
            almacen.borrar()
        }
    }
}
