package com.estudiante.simuladorepidemico.ui.login

import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.contenedorDePrueba
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class LoginViewModelTest {
    private val servidor = ServidorFalso()
    private val contenedor = contenedorDePrueba(servidor)

    @Before
    fun principal() = Dispatchers.setMain(UnconfinedTestDispatcher())

    @After
    fun apagar() {
        servidor.apagar()
        Dispatchers.resetMain()
    }

    private fun LoginViewModel.espera(condicion: (EstadoLogin) -> Boolean): EstadoLogin = runBlocking {
        withTimeout(5_000) {
            while (!condicion(estado)) delay(10)
            estado
        }
    }

    private fun llenar(modelo: LoginViewModel) {
        modelo.espera { it.pregunta != null }
        modelo.cambiarUsuario(" karla ")
        modelo.cambiarPassword("clave")
        modelo.cambiarRespuesta("8")
    }

    @Test
    fun al_abrir_pide_un_captcha() {
        val modelo = LoginViewModel(contenedor.sesion)

        val estado = modelo.espera { it.pregunta != null }

        assertEquals("3 + 5", estado.pregunta)
        assertFalse(estado.listo)
    }

    @Test
    fun entrar_inicia_la_sesion_registra_el_telefono_y_olvida_la_contrasena() {
        val modelo = LoginViewModel(contenedor.sesion)
        llenar(modelo)

        modelo.entrar()

        val estado = modelo.espera { it.dentro }
        assertTrue(runBlocking { contenedor.sesion.activa.first() })
        assertEquals(3L, runBlocking { contenedor.sesion.dispositivo() })
        assertFalse(estado.entrando)
        assertFalse(estado.listo)
        assertEquals("", estado.password)
        assertNull(estado.error)
        val cuerpo = servidor.pedidosA("/api/v1/auth/login").single().body.readUtf8()
        assertTrue(cuerpo.contains("\"usuario\":\"karla\""))
        assertTrue(cuerpo.contains("\"captcha_id\":\"c1\""))
    }

    @Test
    fun si_falla_muestra_el_mensaje_y_pide_otro_captcha() {
        servidor.login = ServidorFalso.problema(401, "CREDENCIALES_INVALIDAS")
        val modelo = LoginViewModel(contenedor.sesion)
        llenar(modelo)

        modelo.entrar()

        val estado = modelo.espera { !it.entrando && it.pregunta != null && it.error != null }
        assertEquals("Detalle de CREDENCIALES_INVALIDAS.", estado.error)
        assertEquals("", estado.respuesta)
        assertEquals("karla", estado.usuario.trim())
        assertEquals(2, servidor.pedidosA("/api/v1/auth/captcha").size)
        assertFalse(estado.dentro)
        assertFalse(runBlocking { contenedor.sesion.activa.first() })
    }

    @Test
    fun sin_red_lo_dice_y_no_deja_entrar() {
        servidor.apagar()
        val modelo = LoginViewModel(contenedor.sesion)

        val estado = modelo.espera { !it.cargandoCaptcha && it.error != null }

        assertEquals("No se pudo conectar con los servicios. Revisa tu conexión.", estado.error)
        assertNull(estado.pregunta)
        modelo.cambiarUsuario("karla")
        modelo.cambiarPassword("clave")
        modelo.cambiarRespuesta("8")
        assertFalse(modelo.estado.listo)
    }

    @Test
    fun no_manda_nada_si_falta_un_campo() {
        val modelo = LoginViewModel(contenedor.sesion)
        modelo.espera { it.pregunta != null }
        modelo.cambiarUsuario("karla")
        modelo.cambiarRespuesta("8")

        modelo.entrar()

        assertTrue(servidor.pedidosA("/api/v1/auth/login").isEmpty())
    }

    @Test
    fun la_respuesta_solo_acepta_digitos() {
        val modelo = LoginViewModel(contenedor.sesion)

        modelo.cambiarRespuesta("1a2 ")

        assertEquals("12", modelo.estado.respuesta)
    }
}
