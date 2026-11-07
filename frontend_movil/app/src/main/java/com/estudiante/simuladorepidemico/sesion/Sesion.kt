package com.estudiante.simuladorepidemico.sesion

import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.red.Captcha
import com.estudiante.simuladorepidemico.red.PedidoLogin
import com.estudiante.simuladorepidemico.red.Perfil
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.Flow
import retrofit2.HttpException
import java.io.IOException

// Los errores del servidor llegan como HttpException; problema() saca su codigo y detail.
class Sesion(
    private val apis: Apis,
    private val almacen: AlmacenSesion,
    private val telefono: Telefono,
) {
    val activa: Flow<Boolean> = almacen.activa

    suspend fun captcha(): Captcha = apis.auth().captcha()

    // Después de cada inicio de sesión el teléfono se registra, o se pone al día si ya lo estaba
    // (README, sección 6). Si no se puede, la sesión sigue: Mi perfil lo dice y deja reintentarlo.
    suspend fun iniciar(usuario: String, password: String, captcha: Captcha, respuesta: String) {
        val login = apis.auth().iniciar(PedidoLogin(usuario, password, captcha.id, respuesta))
        almacen.abrir(login.tokens, login.usuario.id)
        try {
            almacen.guardarDispositivo(telefono.registrar(login.usuario.id, otroSiChoca = true))
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            // Sin registro, dispositivo() queda en null.
        }
    }

    // El id de este teléfono en dispositivos (el device_id de los casos), o null si en esta
    // sesión no se ha podido registrar.
    suspend fun dispositivo(): Long? = almacen.dispositivo()

    // El reintento, con la sesión ya abierta. Aquí un 409 no se resuelve con otro uid: es que
    // revocaron el teléfono, y solo quien vuelva a iniciar sesión con su contraseña puede
    // registrarlo de nuevo. Por eso se cierra la sesión. Una sesión abierta antes de que la app
    // guardara la cuenta pregunta de quién es a /users/me.
    suspend fun registrarTelefono(): Long {
        val cuenta = almacen.cuenta() ?: perfil().id
        val id = try {
            telefono.registrar(cuenta, otroSiChoca = false)
        } catch (e: HttpException) {
            if (e.code() == 409) cerrar()
            throw e
        }
        almacen.guardarDispositivo(id)
        return id
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
