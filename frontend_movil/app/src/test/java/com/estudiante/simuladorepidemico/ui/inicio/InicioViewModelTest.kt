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
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
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
        contenedor.sesion, casos, contenedor.catalogos, contenedor.avisos, contenedor.apis, catalogo, contenedor.programarEnvio, contenedor.programarAvisos,
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
        // Sin roles guardados ni red, la captura se queda: el servidor es quien niega.
        assertTrue(modelo.capturista.value)
    }

    @Test
    fun la_captura_es_solo_del_capturista() = runBlocking<Unit> {
        contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 12, roles = setOf("EPIDEMIOLOGO"))

        assertFalse(withTimeout(5_000) { modelo().capturista.first { !it } })
    }

    @Test
    fun una_sesion_sin_roles_guardados_los_pregunta_al_perfil() = runBlocking<Unit> {
        contenedor.almacen.guardar(tokens("nuevo", "r1"))

        assertEquals(setOf("CAPTURISTA"), contenedor.sesion.roles())
        assertEquals(1, servidor.pedidosA("/api/v1/users/me").size)
    }

    @Test
    fun cuenta_los_avisos_sin_leer() = runBlocking<Unit> {
        servidor.nuevoAviso(7, "La corrida SIM-00042 terminó")
        servidor.nuevoAviso(6, "Versión 2 aprobada")
        val modelo = modelo()

        modelo.contarAvisos()

        assertEquals(2, withTimeout(5_000) { modelo.noLeidos.first { it != null } })
    }

    // ------------------------------------------------------------------ menú por perfil (D56)

    @Test
    fun el_epidemiologo_ve_lo_que_revisa_y_cuenta_por_validar_y_campanas_activas() = runBlocking<Unit> {
        contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 12, roles = setOf("EPIDEMIOLOGO"))

        val modelo = modelo()

        val menu = withTimeout(5_000) { modelo.menu.first { it.revisa } }
        assertFalse(menu.captura || menu.lotesRegistra)
        assertEquals(25, withTimeout(5_000) { modelo.porValidar.first { it != null } })
        assertEquals(2, withTimeout(5_000) { modelo.campanasActivas.first { it != null } })
        val pedido = servidor.pedidosA("/api/v1/cases").first().requestUrl!!
        assertEquals("pendiente" to "1", pedido.queryParameter("status") to pedido.queryParameter("per_page"))
        assertTrue(servidor.pedidosA("/api/v1/cases/incomplete").isEmpty())
    }

    @Test
    fun el_capturista_no_pide_lo_que_es_de_quien_revisa() = runBlocking<Unit> {
        contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 12, roles = setOf("CAPTURISTA"))

        val modelo = modelo()
        modelo.contarAvisos()
        withTimeout(5_000) { modelo.incompletos.first { it != null } }

        assertTrue(servidor.pedidosA("/api/v1/cases").isEmpty() && servidor.pedidosA("/api/v1/campaigns").isEmpty())
    }
}
