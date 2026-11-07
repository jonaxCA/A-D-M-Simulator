package com.estudiante.simuladorepidemico.red

import com.estudiante.simuladorepidemico.CifradorDePrueba
import com.estudiante.simuladorepidemico.Contenedor
import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.datosTemporales
import com.estudiante.simuladorepidemico.tokens
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class RenovadorTest {
    private val servidor = ServidorFalso()
    private val contenedor = Contenedor(datosTemporales(), CifradorDePrueba(), servidor.url)

    @After
    fun apagar() = servidor.apagar()

    private fun iniciarCon(access: String) = runBlocking { contenedor.almacen.guardar(tokens(access, "r1")) }

    private fun guardados() = runBlocking { contenedor.almacen.tokens() }

    private fun perfil() = runBlocking { contenedor.sesion.perfil() }

    @Test
    fun renueva_una_sola_vez_aunque_venzan_varias_a_la_vez() {
        iniciarCon("viejo")
        val juntas = CountDownLatch(5)
        servidor.antesDel401 = {
            juntas.countDown()
            juntas.await(5, TimeUnit.SECONDS)
        }

        val perfiles = runBlocking {
            (1..5).map { async(Dispatchers.IO) { contenedor.sesion.perfil() } }.awaitAll()
        }

        assertEquals(List(5) { "capturista1" }, perfiles.map { it.username })
        assertEquals(1, servidor.renovaciones.get())
        assertEquals(tokens("nuevo", "r2"), guardados())
        val pedido = servidor.pedidosA("/api/v1/sessions/refresh").single()
        assertNull(pedido.getHeader("Authorization"))
        assertTrue(pedido.body.readUtf8().contains("\"r1\""))
    }

    @Test
    fun con_token_revocado_borra_la_sesion_sin_renovar() {
        iniciarCon("viejo")
        servidor.codigo401 = "TOKEN_REVOCADO"

        val error = assertThrows(HttpException::class.java) { perfil() }

        assertEquals("TOKEN_REVOCADO", problema(error).codigo)
        assertNull(guardados())
        assertEquals(0, servidor.renovaciones.get())
    }

    @Test
    fun si_el_refresh_ya_no_sirve_hay_que_iniciar_sesion() {
        iniciarCon("viejo")
        servidor.renovar = ServidorFalso.problema(401, "TOKEN_REVOCADO")

        assertThrows(HttpException::class.java) { perfil() }

        assertNull(guardados())
        assertEquals(1, servidor.renovaciones.get())
    }

    @Test
    fun si_sesiones_no_esta_disponible_conserva_la_sesion() {
        iniciarCon("viejo")
        servidor.renovar = ServidorFalso.problema(503, "SERVICIO_NO_DISPONIBLE")

        assertThrows(HttpException::class.java) { perfil() }

        assertEquals(tokens("viejo", "r1"), guardados())
    }

    @Test
    fun si_ya_hay_otro_access_reintenta_con_el_sin_renovar_ni_borrar() {
        iniciarCon("viejo")
        servidor.codigo401 = "TOKEN_REVOCADO"
        servidor.accessValido = "otro"
        servidor.antesDel401 = { runBlocking { contenedor.almacen.guardar(tokens("otro", "r9")) } }

        assertEquals("capturista1", perfil().username)

        assertEquals(tokens("otro", "r9"), guardados())
        assertEquals(0, servidor.renovaciones.get())
    }
}
