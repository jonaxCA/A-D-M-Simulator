package com.estudiante.simuladorepidemico.ui.casos

import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.tokens
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
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

// D54: los casos del servidor para quien revisa en campo.
@OptIn(ExperimentalCoroutinesApi::class)
class CasosServidorViewModelTest {
    private val servidor = ServidorFalso()
    private val contenedor = contenedorDePrueba(servidor)

    @Before
    fun principal() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        runBlocking { contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 12, roles = setOf("EPIDEMIOLOGO")) }
    }

    @After
    fun apagar() {
        servidor.apagar()
        Dispatchers.resetMain()
    }

    private fun modelo() = CasosServidorViewModel(contenedor.apis)

    private fun CasosServidorViewModel.espera(condicion: (EstadoCasosServidor) -> Boolean) = runBlocking {
        withTimeout(5_000) { while (!condicion(estado)) delay(10) }
        estado
    }

    private fun pedidos() = servidor.pedidosA("/api/v1/cases").map { it.requestUrl!! }

    @Test
    fun empieza_por_los_por_validar_de_veinte_en_veinte() {
        val estado = modelo().espera { !it.cargando && it.pagina > 0 }

        assertEquals(20, estado.casos.size)
        assertEquals(25, estado.total)
        assertTrue(estado.hayMas)
        assertTrue(estado.casos.all { it.status == "pendiente" })
        val pedido = pedidos().single()
        assertEquals(listOf("pendiente", "1", "20"), listOf("status", "page", "per_page").map { pedido.queryParameter(it) })
    }

    @Test
    fun cargar_mas_agrega_la_siguiente_pagina() {
        val modelo = modelo()
        modelo.espera { !it.cargando && it.pagina == 1 }

        modelo.cargar(mas = true)
        val estado = modelo.espera { !it.cargando && it.pagina == 2 }

        assertEquals(25, estado.casos.size)
        assertFalse(estado.hayMas)
        assertEquals(25, estado.casos.map { it.id }.toSet().size)
    }

    @Test
    fun cambiar_el_filtro_vuelve_a_la_primera_pagina() {
        val modelo = modelo()
        modelo.espera { !it.cargando && it.pagina == 1 }

        modelo.filtrar("validado")
        val estado = modelo.espera { !it.cargando && it.filtro == "validado" && it.pagina == 1 }

        assertEquals(listOf(200L, 201L, 202L), estado.casos.map { it.id })
        modelo.filtrar(null)
        val todos = modelo.espera { !it.cargando && it.filtro == null && it.pagina == 1 }
        assertEquals(28, todos.total)
        assertNull(pedidos().last().queryParameter("status"))
    }

    @Test
    fun sin_red_lo_dice() {
        servidor.apagar()

        val estado = modelo().espera { !it.cargando && it.error != null }

        assertTrue(estado.casos.isEmpty())
        assertEquals("No se pudo conectar con los servicios. Revisa tu conexión.", estado.error)
    }
}
