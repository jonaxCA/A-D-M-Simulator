package com.estudiante.simuladorepidemico.sesion

import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.red.json
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException

// El registro del teléfono en dispositivos (README, sección 6), a través de Sesion.
class TelefonoTest {
    private val servidor = ServidorFalso()
    private val contenedor = contenedorDePrueba(servidor)
    private val sesion = contenedor.sesion

    @After
    fun apagar() = servidor.apagar()

    private fun entrar(cuenta: Long = 12) = runBlocking {
        servidor.login = ServidorFalso.respuesta(200, ServidorFalso.cuerpoLogin("a1", "r1", cuenta))
        sesion.iniciar("karla", "clave", sesion.captcha(), "8")
    }

    @Test
    fun al_iniciar_sesion_registra_el_telefono_y_guarda_su_id() = runBlocking<Unit> {
        entrar()

        val pedido = servidor.pedidosA("/api/v1/devices").single()
        assertEquals("Bearer a1", pedido.getHeader("Authorization"))
        val cuerpo = json.parseToJsonElement(pedido.body.readUtf8()).jsonObject
        assertTrue(Regex("[0-9a-f-]{36}").matches(cuerpo["device_uid"]!!.jsonPrimitive.content))
        assertEquals("android", cuerpo["platform"]!!.jsonPrimitive.content)
        assertEquals("Pixel de prueba", cuerpo["model"]!!.jsonPrimitive.content)
        assertEquals("0.1.0", cuerpo["app_version"]!!.jsonPrimitive.content)
        assertEquals(3L, sesion.dispositivo())
    }

    @Test
    fun cada_cuenta_conserva_su_uid_en_el_mismo_telefono() = runBlocking<Unit> {
        entrar(12)
        sesion.cerrar()
        assertNull(sesion.dispositivo())
        entrar(13)
        sesion.cerrar()
        entrar(12)

        val (primera, otra, otraVez) = servidor.uidsEnviados()
        assertNotEquals(primera, otra)
        assertEquals(primera, otraVez)
        assertEquals(3L, sesion.dispositivo())
    }

    @Test
    fun revocado_al_iniciar_sesion_se_registra_con_otro_uid() = runBlocking<Unit> {
        entrar()
        sesion.cerrar()
        servidor.revocados += servidor.uidsEnviados().single()

        entrar()

        val (primera, revocada, nueva) = servidor.uidsEnviados()
        assertEquals(primera, revocada)
        assertNotEquals(primera, nueva)
        assertEquals(4L, sesion.dispositivo())
    }

    @Test
    fun si_dispositivos_falla_la_sesion_se_abre_y_se_reintenta_con_el_mismo_uid() = runBlocking<Unit> {
        servidor.dispositivos = ServidorFalso.problema(503, "SERVICIO_NO_DISPONIBLE")

        entrar()

        assertTrue(sesion.activa.first())
        assertNull(sesion.dispositivo())
        servidor.dispositivos = null
        assertEquals(3L, sesion.registrarTelefono())
        assertEquals(3L, sesion.dispositivo())
        val (fallida, reintento) = servidor.uidsEnviados()
        assertEquals(fallida, reintento)
        // La cuenta quedó guardada al iniciar sesión: no hace falta preguntarla.
        assertTrue(servidor.pedidosA("/api/v1/users/me").isEmpty())
    }

    @Test
    fun revocado_con_la_sesion_abierta_cierra_la_sesion_sin_cambiar_de_uid() {
        entrar()
        servidor.revocados += servidor.uidsEnviados().single()

        val error = assertThrows(HttpException::class.java) { runBlocking { sesion.registrarTelefono() } }

        assertEquals(409, error.code())
        assertFalse(runBlocking { sesion.activa.first() })
        assertNull(runBlocking { sesion.dispositivo() })
        assertEquals(1, servidor.pedidosA("/api/v1/sessions/logout").size)
        assertEquals(1, servidor.uidsEnviados().distinct().size)
        assertNull(runBlocking { contenedor.almacen.cuenta() })
    }

    @Test
    fun la_sesion_guarda_la_cuenta_del_login() = runBlocking<Unit> {
        entrar(13)

        assertEquals(13L, contenedor.almacen.cuenta())
        sesion.cerrar()
        assertNull(contenedor.almacen.cuenta())
    }
}
