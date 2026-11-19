package com.estudiante.simuladorepidemico.avisos

import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.tokens
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AvisosTest {
    private val servidor = ServidorFalso()
    private val contenedor = contenedorDePrueba(servidor)
    private val avisos = contenedor.avisos

    @After
    fun apagar() = servidor.apagar()

    private fun entrar(cuenta: Long) = runBlocking { contenedor.almacen.abrir(tokens("a1", "r1"), cuenta) }

    private fun nuevos() = runBlocking { avisos.nuevos() }.map { it.id }

    @Test
    fun cada_aviso_se_notifica_una_sola_vez() {
        entrar(12)
        servidor.nuevoAviso(7, "La corrida SIM-00042 terminó")
        servidor.nuevoAviso(6, "Versión 2 aprobada")
        servidor.nuevoAviso(5, "Uno ya leído", leido = true)

        assertEquals(listOf(7L, 6L), nuevos())
        assertEquals(emptyList<Long>(), nuevos())
        servidor.nuevoAviso(8, "Otra corrida")
        assertEquals(listOf(8L), nuevos())

        val pedido = servidor.pedidosA("/api/v1/notifications").last()
        assertEquals("true", pedido.requestUrl!!.queryParameter("unread"))
        assertEquals("Bearer a1", pedido.getHeader("Authorization"))
    }

    @Test
    fun lo_que_se_vio_en_la_pantalla_ya_no_se_notifica() {
        entrar(12)
        servidor.nuevoAviso(7, "La corrida SIM-00042 terminó")

        val lista = runBlocking { avisos.lista() }

        assertEquals(1, lista.noLeidas)
        assertEquals(emptyList<Long>(), nuevos())
    }

    @Test
    fun otra_cuenta_en_el_mismo_telefono_lleva_su_cuenta() {
        entrar(12)
        servidor.nuevoAviso(7, "Para la 12")
        nuevos()

        entrar(13)

        assertEquals(listOf(7L), nuevos())
    }

    @Test
    fun sin_sesion_no_pregunta_nada() {
        servidor.nuevoAviso(7, "La corrida SIM-00042 terminó")

        assertEquals(emptyList<Long>(), nuevos())
        assertTrue(servidor.pedidosA("/api/v1/notifications").isEmpty())
    }
}
