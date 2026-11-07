package com.estudiante.simuladorepidemico.sesion

import com.estudiante.simuladorepidemico.CifradorDePrueba
import com.estudiante.simuladorepidemico.Contenedor
import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.datosTemporales
import com.estudiante.simuladorepidemico.red.Perfil
import com.estudiante.simuladorepidemico.red.json
import com.estudiante.simuladorepidemico.red.problema
import com.estudiante.simuladorepidemico.tokens
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException

class SesionTest {
    private val servidor = ServidorFalso()
    private val contenedor = Contenedor(datosTemporales(), CifradorDePrueba(), servidor.url)
    private val sesion = contenedor.sesion

    @After
    fun apagar() = servidor.apagar()

    @Test
    fun iniciar_manda_el_captcha_y_guarda_los_tokens() = runBlocking<Unit> {
        sesion.iniciar("karla", "clave", sesion.captcha(), "8")

        val pedido = servidor.pedidosA("/api/v1/auth/login").single()
        val cuerpo = json.parseToJsonElement(pedido.body.readUtf8()).jsonObject
        assertEquals("c1", cuerpo["captcha_id"]!!.jsonPrimitive.content)
        assertEquals("8", cuerpo["captcha_respuesta"]!!.jsonPrimitive.content)
        assertNull(pedido.getHeader("Authorization"))
        assertEquals(tokens("a1", "r1"), contenedor.almacen.tokens())
        assertTrue(sesion.activa.first())
    }

    @Test
    fun con_credenciales_malas_no_guarda_nada() {
        servidor.login = ServidorFalso.problema(401, "CREDENCIALES_INVALIDAS")

        val error = assertThrows(HttpException::class.java) {
            runBlocking { sesion.iniciar("karla", "mala", sesion.captcha(), "8") }
        }

        assertEquals("CREDENCIALES_INVALIDAS", problema(error).codigo)
        assertNull(runBlocking { contenedor.almacen.tokens() })
    }

    @Test
    fun el_perfil_se_pide_en_json_con_el_access() = runBlocking<Unit> {
        contenedor.almacen.guardar(tokens("nuevo", "r1"))

        assertEquals(
            Perfil(12, "capturista1", "Carla Captura", "c@ejemplo.mx", null, listOf("CAPTURISTA")),
            sesion.perfil(),
        )
        val pedido = servidor.pedidosA("/api/v1/users/me").single()
        assertEquals("Bearer nuevo", pedido.getHeader("Authorization"))
        assertEquals("application/json", pedido.getHeader("Accept"))
    }

    @Test
    fun cerrar_avisa_al_servidor_y_borra() = runBlocking<Unit> {
        contenedor.almacen.guardar(tokens("nuevo", "r1"))

        sesion.cerrar()

        val pedido = servidor.pedidosA("/api/v1/sessions/logout").single()
        assertEquals("Bearer nuevo", pedido.getHeader("Authorization"))
        assertNull(contenedor.almacen.tokens())
        assertFalse(sesion.activa.first())
    }

    @Test
    fun cerrar_sin_red_tambien_borra() = runBlocking<Unit> {
        contenedor.almacen.guardar(tokens("nuevo", "r1"))
        servidor.apagar()

        sesion.cerrar()

        assertNull(contenedor.almacen.tokens())
    }
}
