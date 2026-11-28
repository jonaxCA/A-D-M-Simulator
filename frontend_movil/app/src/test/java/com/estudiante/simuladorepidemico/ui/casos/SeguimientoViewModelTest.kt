package com.estudiante.simuladorepidemico.ui.casos

import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.red.json
import com.estudiante.simuladorepidemico.tokens
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.jsonObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class SeguimientoViewModelTest {
    private val servidor = ServidorFalso()
    private val contenedor = contenedorDePrueba(servidor)

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

    private fun modelo() = SeguimientoViewModel(contenedor.apis, contenedor.sesion, 41)

    private fun SeguimientoViewModel.espera(condicion: (EstadoSeguimiento) -> Boolean) = runBlocking {
        withTimeout(5_000) { while (!condicion(estado)) delay(10) }
        estado
    }

    @Test
    fun muestra_el_estado_del_servidor_y_su_historial() {
        val estado = modelo().espera { !it.cargando }

        assertEquals("pendiente", estado.caso!!.status)
        assertTrue(estado.puedeCorregir)
        assertEquals("edad: 33 → 34", textoDeCambios(estado.historial.single().cambios))
    }

    @Test
    fun corrige_solo_lo_que_cambio_con_la_version_que_leyo() {
        val modelo = modelo()
        modelo.espera { !it.cargando }

        modelo.corregir()
        modelo.cambiar { copy(edad = "35", motivo = "Edad mal capturada") }
        modelo.guardar()
        val estado = modelo.espera { !it.cargando && it.correccion == null }

        val pedido = servidor.correcciones.single()
        assertEquals("\"1\"", pedido.getHeader("If-Match"))
        val cuerpo = json.parseToJsonElement(pedido.body.readUtf8()).jsonObject
        assertEquals(setOf("age", "reason"), cuerpo.keys)
        assertEquals(2, estado.caso!!.version)
        assertNull(estado.conflicto)
    }

    @Test
    fun si_otra_persona_lo_cambio_no_lo_pisa_y_muestra_como_quedo() {
        val modelo = modelo()
        modelo.espera { !it.cargando }
        servidor.versionRemota = 2

        modelo.corregir()
        modelo.cambiar { copy(edad = "35") }
        modelo.guardar()
        val estado = modelo.espera { it.conflicto != null }

        assertEquals("Detalle de CONFLICTO.", estado.conflicto)
        assertEquals(2, estado.caso!!.version)
        assertNull(estado.correccion)
    }

    @Test
    fun sin_cambios_no_manda_nada() {
        val modelo = modelo()
        modelo.espera { !it.cargando }

        modelo.corregir()
        modelo.guardar()

        assertTrue(servidor.correcciones.isEmpty())
        assertNull(modelo.estado.correccion)
    }

    @Test
    fun un_caso_ajeno_no_se_puede_corregir() {
        runBlocking { contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 99) }

        assertFalse(modelo().espera { !it.cargando }.puedeCorregir)
    }

    // ------------------------------------------------------------------ fotos (D30)

    private fun SeguimientoViewModel.primeraFoto() = espera { it.fotos.isNotEmpty() }.fotos.first()

    @Test
    fun lista_las_fotos_del_caso_con_su_tipo() {
        val estado = modelo().espera { it.fotos.isNotEmpty() }

        assertEquals(listOf(12L, 13L), estado.fotos.map { it.id })
        assertEquals(listOf("image/jpeg", "application/pdf"), estado.fotos.map { it.tipo })
        assertNull(estado.errorFotos)
    }

    @Test
    fun ve_una_foto_con_su_url_firmada_sin_mandar_el_token_al_bucket() {
        val modelo = modelo()

        modelo.verFoto(modelo.primeraFoto())
        val estado = modelo.espera { it.fotoAbierta != null || it.errorFotos != null }

        assertTrue(estado.fotoAbierta!!.bytes.contentEquals(servidor.fotoEnBucket))
        assertEquals("Bearer a1", servidor.pedidosA("/api/v1/attachments/12/url").single().getHeader("Authorization"))
        val alBucket = servidor.pedidos.single { it.path.orEmpty().startsWith("/bucket/") }
        assertNull(alBucket.getHeader("Authorization"))
        modelo.cerrarFoto()
        assertNull(modelo.estado.fotoAbierta)
    }

    @Test
    fun si_lo_que_llega_no_coincide_con_la_huella_no_lo_muestra() {
        servidor.huellaDeLaFoto = "a".repeat(64)
        val modelo = modelo()

        modelo.verFoto(modelo.primeraFoto())
        val estado = modelo.espera { it.bajandoFoto == null && (it.fotoAbierta != null || it.errorFotos != null) }

        assertNull(estado.fotoAbierta)
        assertEquals("La foto que llegó no coincide con la del servidor; no se muestra.", estado.errorFotos)
    }

    @Test
    fun si_el_bucket_no_responde_lo_dice_y_se_puede_reintentar() {
        servidor.bucketResponde = 403
        val modelo = modelo()
        val foto = modelo.primeraFoto()

        modelo.verFoto(foto)
        val estado = modelo.espera { it.bajandoFoto == null && it.errorFotos != null }
        assertNull(estado.fotoAbierta)

        servidor.bucketResponde = 200
        modelo.verFoto(foto)
        assertEquals(12L, modelo.espera { it.fotoAbierta != null }.fotoAbierta!!.id)
    }

    @Test
    fun si_evidencias_no_responde_el_caso_se_sigue_viendo() {
        servidor.listaDeFotos = ServidorFalso.problema(503, "SERVICIO_NO_DISPONIBLE")

        val estado = modelo().espera { it.errorFotos != null }

        assertEquals("pendiente", estado.caso!!.status)
        assertTrue(estado.fotos.isEmpty())
        assertTrue(estado.errorFotos!!.startsWith("No se pudieron consultar las fotos"))
    }

    @Test
    fun no_baja_un_archivo_mas_grande_que_el_tope() {
        val url = servidor.url + "bucket/evidencias/41/12.jpg"

        val error = runCatching { runBlocking { contenedor.apis.bajarFirmada(url, maximo = 4) } }.exceptionOrNull()

        assertTrue(error is IOException)
        assertEquals(servidor.fotoEnBucket.size, runBlocking { contenedor.apis.bajarFirmada(url) }.size)
    }

    @Test
    fun el_tamano_se_lee_en_kb_o_mb() {
        assertNull(tamanoLegible(0))
        assertEquals("2 KB", tamanoLegible(1500))
        assertEquals("1.8 MB", tamanoLegible(1_843_200))
    }

    @Test
    fun si_el_perfil_no_ve_fotos_no_es_un_error() {
        servidor.listaDeFotos = ServidorFalso.problema(403, "PERMISO_INSUFICIENTE")

        val estado = modelo().espera { it.fotosSinAcceso }

        assertNull(estado.errorFotos)
        assertTrue(estado.fotos.isEmpty())
    }
}
