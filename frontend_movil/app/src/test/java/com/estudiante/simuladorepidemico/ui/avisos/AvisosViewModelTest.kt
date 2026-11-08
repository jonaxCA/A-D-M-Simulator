package com.estudiante.simuladorepidemico.ui.avisos

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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AvisosViewModelTest {
    private val servidor = ServidorFalso()
    private val contenedor = contenedorDePrueba(servidor)

    @Before
    fun principal() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        runBlocking { contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 12) }
        servidor.nuevoAviso(7, "La corrida SIM-00042 terminó")
        servidor.nuevoAviso(6, "Versión 2 aprobada")
        servidor.nuevoAviso(5, "Uno viejo", leido = true)
    }

    @After
    fun apagar() {
        servidor.apagar()
        Dispatchers.resetMain()
    }

    private fun AvisosViewModel.espera(condicion: (EstadoAvisos) -> Boolean): EstadoAvisos = runBlocking {
        withTimeout(5_000) {
            while (!condicion(estado)) delay(10)
            estado
        }
    }

    private fun marcados() = servidor.pedidos.filter { it.path.orEmpty().endsWith("/read") }.map { it.path!!.substringBefore('?') }

    @Test
    fun carga_los_de_la_cuenta_del_mas_nuevo_al_mas_viejo() {
        val estado = AvisosViewModel(contenedor.avisos).espera { !it.cargando }

        assertEquals(listOf(7L, 6L, 5L), estado.avisos.map { it.id })
        assertEquals(2, estado.noLeidos)
        assertEquals(listOf(false, false, true), estado.avisos.map { it.leido })
    }

    @Test
    fun abrir_uno_sin_leer_lo_marca_y_uno_leido_no_manda_nada() {
        val modelo = AvisosViewModel(contenedor.avisos)
        val estado = modelo.espera { !it.cargando }

        modelo.abrir(estado.avisos.first { it.id == 5L })
        modelo.abrir(estado.avisos.first { it.id == 7L })

        val despues = modelo.espera { it.noLeidos == 1 }
        assertTrue(despues.avisos.first { it.id == 7L }.leido)
        assertEquals(listOf("/api/v1/notifications/7/read"), marcados())
    }

    @Test
    fun marcar_todos_solo_manda_los_que_faltan() {
        val modelo = AvisosViewModel(contenedor.avisos)
        modelo.espera { !it.cargando }

        modelo.marcarTodos()

        val estado = modelo.espera { !it.marcandoTodos && it.noLeidos == 0 }
        assertTrue(estado.avisos.all { it.leido })
        assertEquals(listOf("/api/v1/notifications/7/read", "/api/v1/notifications/6/read"), marcados())
    }

    @Test
    fun sin_red_lo_dice() {
        servidor.apagar()

        val estado = AvisosViewModel(contenedor.avisos).espera { !it.cargando }

        assertEquals("Sin conexión: los avisos se consultan con red.", estado.error)
        assertTrue(estado.avisos.isEmpty())
    }
}
