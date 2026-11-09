package com.estudiante.simuladorepidemico.ui.inicio

import com.estudiante.simuladorepidemico.CasosDaoFalso
import com.estudiante.simuladorepidemico.CatalogoDaoFalso
import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.casoDePrueba
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.tokens
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
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
class InicioViewModelTest {
    private val servidor = ServidorFalso()
    private val casos = CasosDaoFalso()
    private val catalogo = CatalogoDaoFalso()
    private var envios = 0
    private var consultas = 0
    private val contenedor = contenedorDePrueba(servidor, casos, catalogo, programarAvisos = { consultas++ }) { envios++ }

    private fun modelo() = InicioViewModel(
        contenedor.sesion, casos, contenedor.catalogos, contenedor.avisos, contenedor.programarEnvio, contenedor.programarAvisos,
    )

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

    @Test
    fun al_llegar_pide_el_envio_baja_los_catalogos_y_cuenta_lo_pendiente() = runBlocking<Unit> {
        casos.insertar(casoDePrueba("a"))

        val modelo = modelo()

        assertEquals(1 to 1, envios to consultas)
        assertEquals(1, withTimeout(5_000) { modelo.porEnviar.first { it > 0 } })
        withTimeout(5_000) { catalogo.listaMunicipios.first { it.isNotEmpty() } }
        assertEquals(2, catalogo.listaEnfermedades.value.size)
    }

    @Test
    fun sin_red_el_inicio_abre_igual() = runBlocking<Unit> {
        servidor.apagar()

        val modelo = modelo()
        modelo.contarAvisos()

        assertEquals(0, modelo.porEnviar.value)
        assertEquals(null, modelo.noLeidos.value)
        assertEquals(1, envios)
    }

    @Test
    fun cuenta_los_avisos_sin_leer() = runBlocking<Unit> {
        servidor.nuevoAviso(7, "La corrida SIM-00042 terminó")
        servidor.nuevoAviso(6, "Versión 2 aprobada")
        val modelo = modelo()

        modelo.contarAvisos()

        assertEquals(2, withTimeout(5_000) { modelo.noLeidos.first { it != null } })
    }
}
