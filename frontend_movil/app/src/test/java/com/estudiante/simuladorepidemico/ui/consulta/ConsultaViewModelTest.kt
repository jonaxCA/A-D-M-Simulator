package com.estudiante.simuladorepidemico.ui.consulta

import com.estudiante.simuladorepidemico.CatalogoDaoFalso
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
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ConsultaViewModelTest {
    private val servidor = ServidorFalso()
    private val catalogo = CatalogoDaoFalso()
    private val contenedor = contenedorDePrueba(servidor, catalogo = catalogo)

    @Before
    fun principal() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        runBlocking { contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 12) }
    }

    @After
    fun apagar() {
        servidor.apagar()
        Dispatchers.resetMain()
    }

    private fun ConsultaViewModel.espera(condicion: (EstadoConsulta) -> Boolean) = runBlocking {
        withTimeout(5_000) { while (!condicion(estado)) delay(10) }
        estado
    }

    @Test
    fun pide_las_zonas_de_la_enfermedad_y_el_periodo_elegidos() {
        val modelo = ConsultaViewModel(contenedor.apis, catalogo)
        modelo.espera { it.zonas != null }

        modelo.elegirEnfermedad(2)
        modelo.elegirPeriodo(90)
        val estado = modelo.espera { !it.cargando }

        assertEquals("Monterrey", estado.zonas!!.single().zona)
        val ultima = servidor.pedidosA("/api/v1/zones").last().requestUrl!!
        assertEquals("2" to "90", ultima.queryParameter("disease_id") to ultima.queryParameter("days"))
    }

    @Test
    fun sin_red_lo_dice() {
        servidor.apagar()

        val estado = ConsultaViewModel(contenedor.apis, catalogo).espera { it.error != null }

        assertEquals("No se pudo conectar con los servicios. Revisa tu conexión.", estado.error)
    }
}
