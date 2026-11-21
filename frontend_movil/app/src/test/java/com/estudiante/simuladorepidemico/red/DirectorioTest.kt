package com.estudiante.simuladorepidemico.red

import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.red.api.EstadoServiciosApi
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import java.io.IOException

class DirectorioTest {
    private val servidor = ServidorFalso()
    private val directorio =
        Directorio(retrofit(servidor.url, clienteBase()).create(EstadoServiciosApi::class.java))

    @After
    fun apagar() = servidor.apagar()

    @Test
    fun pide_el_directorio_una_sola_vez_y_en_json() {
        assertEquals(servidor.url, directorio.url("auth"))
        assertEquals(servidor.url, directorio.url("usuarios"))

        val pedido = servidor.pedidosA("/api/v1/services").single()
        assertEquals("application/json", pedido.getHeader("Accept"))
    }

    @Test
    fun un_servicio_que_no_esta_es_error_de_red() {
        assertThrows(IOException::class.java) { directorio.url("no-existe") }
    }

    @Test
    fun sin_directorio_es_error_de_red() {
        servidor.apagar()
        assertThrows(IOException::class.java) { directorio.url("auth") }
    }
}
