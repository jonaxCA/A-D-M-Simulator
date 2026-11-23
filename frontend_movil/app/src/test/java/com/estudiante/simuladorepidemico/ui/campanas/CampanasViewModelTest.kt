package com.estudiante.simuladorepidemico.ui.campanas

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
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

// D49 y D54: las campañas para consultarlas en campo.
@OptIn(ExperimentalCoroutinesApi::class)
class CampanasViewModelTest {
    private val servidor = ServidorFalso()
    private val contenedor = contenedorDePrueba(servidor)

    @Before
    fun principal() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        runBlocking { contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 12, roles = setOf("AUTORIDAD_SANITARIA")) }
    }

    @After
    fun apagar() {
        servidor.apagar()
        Dispatchers.resetMain()
    }

    private fun CampanasViewModel.espera(condicion: (EstadoCampanas) -> Boolean) = runBlocking {
        withTimeout(5_000) { while (!condicion(estado)) delay(10) }
        estado
    }

    @Test
    fun empieza_por_las_activas() {
        val estado = CampanasViewModel(contenedor.apis).espera { !it.cargando && it.campanas != null }

        assertEquals(listOf(3L, 5L), estado.campanas!!.map { it.id })
        assertEquals("Nuevo León", estado.campanas.first().municipio)
        assertEquals(120000L, estado.campanas.first().poblacionObjetivo)
        assertEquals("activa", servidor.pedidosA("/api/v1/campaigns").single().requestUrl!!.queryParameter("status"))
    }

    @Test
    fun todas_las_pide_sin_filtro() {
        val modelo = CampanasViewModel(contenedor.apis)
        modelo.espera { !it.cargando && it.campanas != null }

        modelo.filtrar(null)
        val estado = modelo.espera { !it.cargando && it.filtro == null && it.campanas?.size == 3 }

        assertEquals(3, estado.campanas!!.size)
        assertNull(servidor.pedidosA("/api/v1/campaigns").last().requestUrl!!.queryParameter("status"))
    }

    @Test
    fun la_poblacion_se_lee_con_separador_de_miles() {
        assertEquals("120,000", poblacion(120000))
    }
}
