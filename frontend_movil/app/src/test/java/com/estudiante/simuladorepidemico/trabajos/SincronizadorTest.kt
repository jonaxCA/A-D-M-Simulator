package com.estudiante.simuladorepidemico.trabajos

import com.estudiante.simuladorepidemico.CasosDaoFalso
import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.casoDePrueba
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.local.EstadoCaso
import com.estudiante.simuladorepidemico.local.EstadoFoto
import com.estudiante.simuladorepidemico.local.FotoLocal
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SincronizadorTest {
    private val servidor = ServidorFalso()
    private val casos = CasosDaoFalso()
    private val contenedor = contenedorDePrueba(servidor, casos)
    private val sesion = contenedor.sesion

    @After
    fun apagar() = servidor.apagar()

    private fun entrar() = runBlocking { sesion.iniciar("karla", "clave", sesion.captcha(), "8") }

    private fun capturar(vararg uuids: String, cuenta: Long = 12, municipio: Long = 10) = runBlocking {
        uuids.forEachIndexed { i, uuid -> casos.insertar(casoDePrueba(uuid, cuenta, capturadoEn = i + 1L, municipio = municipio)) }
    }

    private fun enviar() = runBlocking { contenedor.sincronizador.enviar() }

    private fun uuid(n: Int) = "00000000-0000-4000-8000-%012d".format(n)

    @Test
    fun manda_los_pendientes_de_la_cuenta_en_un_lote_con_el_telefono() {
        entrar()
        runBlocking {
            casos.insertar(
                casoDePrueba(uuid(1)).copy(
                    edad = 34, sexo = "F", severidad = "leve", inicioSintomas = "2026-11-03",
                    latitud = 25.686613, longitud = -100.316116,
                )
            )
        }
        capturar(uuid(2))
        capturar(uuid(3), cuenta = 13)

        assertEquals(Envio.LISTO, enviar())

        val lote = servidor.lotesEnviados().single()
        assertEquals(3L, lote["device_id"]!!.jsonPrimitive.long)
        val enviados = lote["cases"]!!.jsonArray.map { it.jsonObject }
        assertEquals(listOf(uuid(1), uuid(2)), enviados.map { it["local_uuid"]!!.jsonPrimitive.content })
        val primero = enviados[0]
        assertEquals(34, primero["age"]!!.jsonPrimitive.int)
        assertEquals("F", primero["sex"]!!.jsonPrimitive.content)
        assertEquals("2026-11-03", primero["onset_date"]!!.jsonPrimitive.content)
        assertEquals("2026-11-05", primero["report_date"]!!.jsonPrimitive.content)
        assertEquals(25.686613 to -100.316116, primero["latitude"]!!.jsonPrimitive.double to primero["longitude"]!!.jsonPrimitive.double)
        // Lo que no se capturó no viaja, ni como null.
        assertFalse("age" in enviados[1] || "latitude" in enviados[1])
        assertEquals(EstadoCaso.ENVIADO to 41L, casos.caso(uuid(1)).let { it.estado to it.caseId })
        assertEquals(42L, casos.caso(uuid(2)).caseId)
        assertNull(casos.caso(uuid(1)).edad)
        assertEquals(EstadoCaso.PENDIENTE, casos.caso(uuid(3)).estado)
    }

    @Test
    fun mas_de_cien_van_en_varios_lotes() {
        entrar()
        capturar(*Array(150) { uuid(it) })

        assertEquals(Envio.LISTO, enviar())

        val lotes = servidor.lotesEnviados()
        assertEquals(listOf(100, 50), lotes.map { it["cases"]!!.jsonArray.size })
        assertNotEquals(lotes[0]["batch_id"], lotes[1]["batch_id"])
        assertEquals(0, runBlocking { casos.porEnviar(12).first() })
    }

    @Test
    fun sin_respuesta_reintenta_el_mismo_lote() {
        entrar()
        capturar(uuid(1))
        servidor.lote = ServidorFalso.problema(503, "SERVICIO_NO_DISPONIBLE")

        assertEquals(Envio.REINTENTAR, enviar())
        assertEquals(EstadoCaso.PENDIENTE, casos.caso(uuid(1)).estado)
        servidor.lote = null
        assertEquals(Envio.LISTO, enviar())

        val (fallido, reintento) = servidor.lotesEnviados()
        assertEquals(fallido["batch_id"], reintento["batch_id"])
        assertEquals(EstadoCaso.ENVIADO, casos.caso(uuid(1)).estado)
    }

    @Test
    fun un_caso_con_datos_malos_queda_rechazado_con_el_motivo() {
        entrar()
        capturar(uuid(1))
        capturar(uuid(2), municipio = 999)

        assertEquals(Envio.LISTO, enviar())

        assertEquals(EstadoCaso.ENVIADO, casos.caso(uuid(1)).estado)
        val rechazado = casos.caso(uuid(2))
        assertEquals(EstadoCaso.RECHAZADO, rechazado.estado)
        assertEquals("Ese municipio no está en el catálogo de Nuevo León.", rechazado.error)
        assertNull(rechazado.lote)
    }

    @Test
    fun telefono_revocado_devuelve_los_casos_y_cierra_la_sesion() {
        entrar()
        capturar(uuid(1), uuid(2))
        servidor.telefonoRevocado = true
        servidor.revocados += servidor.uidsEnviados().single()

        assertEquals(Envio.SIN_SESION, enviar())

        listOf(uuid(1), uuid(2)).map(casos::caso).forEach {
            assertEquals(EstadoCaso.PENDIENTE, it.estado)
            assertNull(it.lote)
            assertNull(it.error)
        }
        assertFalse(runBlocking { sesion.activa.first() })
        assertEquals(1, servidor.pedidosA("/api/v1/sessions/logout").size)

        // Al volver a entrar, el teléfono queda registrado con otro uid y los casos van en otro lote.
        servidor.telefonoRevocado = false
        entrar()
        assertEquals(Envio.LISTO, enviar())
        val (revocado, nuevo) = servidor.lotesEnviados()
        assertNotEquals(revocado["batch_id"], nuevo["batch_id"])
        assertEquals(4L, nuevo["device_id"]!!.jsonPrimitive.long)
        assertEquals(EstadoCaso.ENVIADO, casos.caso(uuid(1)).estado)
    }

    @Test
    fun sin_telefono_registrado_lo_registra_antes_de_enviar() {
        servidor.dispositivos = ServidorFalso.problema(503, "SERVICIO_NO_DISPONIBLE")
        entrar()
        servidor.dispositivos = null
        capturar(uuid(1))

        assertEquals(Envio.LISTO, enviar())

        assertEquals(2, servidor.pedidosA("/api/v1/devices").size)
        assertEquals(3L, servidor.lotesEnviados().single()["device_id"]!!.jsonPrimitive.long)
    }

    @Test
    fun si_el_rol_no_puede_registrar_casos_quedan_rechazados() {
        entrar()
        capturar(uuid(1))
        servidor.lote = ServidorFalso.problema(403, "PERMISO_INSUFICIENTE")

        assertEquals(Envio.LISTO, enviar())

        assertEquals(EstadoCaso.RECHAZADO, casos.caso(uuid(1)).estado)
        assertEquals("Detalle de PERMISO_INSUFICIENTE.", casos.caso(uuid(1)).error)
    }

    @Test
    fun sin_sesion_no_manda_nada() {
        capturar(uuid(1))

        assertEquals(Envio.SIN_SESION, enviar())

        assertTrue(servidor.pedidosA("/api/v1/sync/cases").isEmpty())
        assertEquals(EstadoCaso.PENDIENTE, casos.caso(uuid(1)).estado)
    }
    // Un caso con dos fotos, ya guardadas como las deja el formulario.
    private fun capturarConFotos(uuid: String, vararg contenidos: String): List<String> = runBlocking {
        val ids = contenidos.mapIndexed { i, contenido ->
            val id = "foto-$uuid-$i"
            contenedor.fotos.archivo(id).apply { parentFile!!.mkdirs() }.writeText(contenido)
            id
        }
        casos.capturar(casoDePrueba(uuid), ids.mapIndexed { i, id -> FotoLocal(id, uuid, tomadaEn = i.toLong()) })
        ids
    }

    @Test
    fun las_fotos_se_suben_cuando_el_caso_ya_tiene_case_id_y_se_borran_del_telefono() {
        entrar()
        val (a, b) = capturarConFotos(uuid(1), "foto a", "foto b")
        servidor.lote = ServidorFalso.problema(503, "SERVICIO_NO_DISPONIBLE")

        // Sin case_id no hay a dónde subirlas.
        assertEquals(Envio.REINTENTAR, enviar())
        assertTrue(servidor.subidas().isEmpty())
        servidor.lote = null
        assertEquals(Envio.LISTO, enviar())

        val subidas = servidor.subidas()
        assertEquals(listOf(41L, 41L), subidas.map { it.first })
        assertEquals(listOf("foto a", "foto b"), subidas.map { it.second.body.readUtf8() })
        assertEquals("image/jpeg", subidas[0].second.getHeader("Content-Type"))
        assertEquals("Bearer a1", subidas[0].second.getHeader("Authorization"))
        assertEquals(EstadoFoto.SUBIDA to 12L, casos.foto(a).let { it.estado to it.evidencia })
        assertEquals(13L, casos.foto(b).evidencia)
        assertFalse(contenedor.fotos.archivo(a).exists() || contenedor.fotos.archivo(b).exists())
        // La siguiente corrida ya no las vuelve a subir.
        assertEquals(Envio.LISTO, enviar())
        assertEquals(2, servidor.subidas().size)
    }

    @Test
    fun una_foto_sin_respuesta_se_reintenta_y_una_rechazada_queda_con_su_motivo() {
        entrar()
        val (foto) = capturarConFotos(uuid(1), "foto a")
        servidor.evidencia = ServidorFalso.problema(503, "SERVICIO_NO_DISPONIBLE")

        assertEquals(Envio.REINTENTAR, enviar())
        assertEquals(EstadoFoto.PENDIENTE, casos.foto(foto).estado)
        assertTrue(contenedor.fotos.archivo(foto).exists())
        // El caso sí se envió: no se vuelve a mandar en otro lote.
        assertEquals(EstadoCaso.ENVIADO, casos.caso(uuid(1)).estado)

        servidor.evidencia = ServidorFalso.problema(422, "DATOS_INVALIDOS")
        assertEquals(Envio.LISTO, enviar())

        assertEquals(EstadoFoto.RECHAZADA to "Detalle de DATOS_INVALIDOS.", casos.foto(foto).let { it.estado to it.error })
        assertFalse(contenedor.fotos.archivo(foto).exists())
        assertEquals(1, servidor.lotesEnviados().size)
    }

    @Test
    fun una_foto_cuyo_archivo_ya_no_esta_queda_rechazada() {
        entrar()
        val (foto) = capturarConFotos(uuid(1), "foto a")
        contenedor.fotos.archivo(foto).delete()

        assertEquals(Envio.LISTO, enviar())

        assertEquals(EstadoFoto.RECHAZADA, casos.foto(foto).estado)
        assertTrue(servidor.subidas().isEmpty())
    }
}
