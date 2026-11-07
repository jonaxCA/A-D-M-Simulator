package com.estudiante.simuladorepidemico.ui.perfil

import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.tokens
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
class PerfilViewModelTest {
    private val servidor = ServidorFalso()
    private val contenedor = contenedorDePrueba(servidor)

    @Before
    fun principal() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        runBlocking { contenedor.almacen.guardar(tokens("nuevo", "r1")) }
    }

    @After
    fun apagar() {
        servidor.apagar()
        Dispatchers.resetMain()
    }

    private fun PerfilViewModel.espera(condicion: (EstadoPerfil) -> Boolean): EstadoPerfil = runBlocking {
        withTimeout(5_000) {
            while (!condicion(estado)) delay(10)
            estado
        }
    }

    @Test
    fun carga_la_cuenta_del_token_y_cuando_vence_la_sesion() {
        val estado = PerfilViewModel(contenedor.sesion).espera { !it.cargando }

        assertEquals("Carla Captura", estado.perfil?.nombre)
        assertEquals(listOf("CAPTURISTA"), estado.perfil?.roles)
        assertEquals(1_800_000_000L, estado.vence)
        assertNull(estado.error)
        assertNull(estado.dispositivo)
        assertEquals("Bearer nuevo", servidor.pedidosA("/api/v1/users/me").single().getHeader("Authorization"))
    }

    @Test
    fun registra_el_telefono_que_no_quedo_registrado() {
        val modelo = PerfilViewModel(contenedor.sesion)
        modelo.espera { !it.cargando }

        modelo.registrarTelefono()
        modelo.registrarTelefono()

        val estado = modelo.espera { !it.registrando }
        assertEquals(3L, estado.dispositivo)
        assertNull(estado.errorTelefono)
        assertEquals(1, servidor.pedidosA("/api/v1/devices").size)
        assertEquals(3L, runBlocking { contenedor.sesion.dispositivo() })
    }

    @Test
    fun si_no_se_puede_registrar_lo_dice() {
        servidor.dispositivos = ServidorFalso.problema(503, "SERVICIO_NO_DISPONIBLE")
        val modelo = PerfilViewModel(contenedor.sesion)
        modelo.espera { !it.cargando }

        modelo.registrarTelefono()

        val estado = modelo.espera { !it.registrando }
        assertNull(estado.dispositivo)
        assertEquals("Detalle de SERVICIO_NO_DISPONIBLE.", estado.errorTelefono)
        assertTrue(runBlocking { contenedor.sesion.activa.first() })
    }

    @Test
    fun sin_red_lo_dice_y_reintenta() {
        servidor.apagar()
        val modelo = PerfilViewModel(contenedor.sesion)

        val estado = modelo.espera { !it.cargando }

        assertNull(estado.perfil)
        assertEquals("No se pudo conectar con los servicios. Revisa tu conexión.", estado.error)
        modelo.cargar()
        assertEquals("No se pudo conectar con los servicios. Revisa tu conexión.", modelo.espera { !it.cargando }.error)
    }

    @Test
    fun cerrar_sesion_avisa_al_servidor_y_borra_la_sesion() {
        val modelo = PerfilViewModel(contenedor.sesion)
        modelo.espera { !it.cargando }

        modelo.cerrarSesion()
        modelo.cerrarSesion()

        assertFalse(runBlocking { withTimeout(5_000) { contenedor.sesion.activa.first { !it } } })
        assertEquals(1, servidor.pedidosA("/api/v1/sessions/logout").size)
    }
}
