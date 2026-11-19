package com.estudiante.simuladorepidemico.sesion

import androidx.datastore.preferences.core.stringPreferencesKey
import com.estudiante.simuladorepidemico.CifradorDePrueba
import com.estudiante.simuladorepidemico.datosTemporales
import com.estudiante.simuladorepidemico.tokens
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AlmacenSesionTest {
    private val datos = datosTemporales()
    private val cifrador = CifradorDePrueba()

    @Test
    fun guarda_cifrado_y_otra_instancia_lo_lee() = runBlocking<Unit> {
        AlmacenSesion(datos, cifrador).guardar(tokens("a1", "r1"))

        val crudo = datos.data.first()[stringPreferencesKey("tokens")]!!
        assertTrue(crudo.startsWith("cifrado:"))
        assertFalse(crudo.contains("refresh_token"))
        assertEquals(tokens("a1", "r1"), AlmacenSesion(datos, cifrador).tokens())
    }

    @Test
    fun sin_la_llave_no_hay_sesion() = runBlocking<Unit> {
        AlmacenSesion(datos, cifrador).guardar(tokens("a1", "r1"))
        cifrador.sinLlave = true

        assertNull(AlmacenSesion(datos, cifrador).tokens())
    }

    @Test
    fun borrar_cierra_la_sesion() = runBlocking<Unit> {
        val almacen = AlmacenSesion(datos, cifrador)
        almacen.guardar(tokens("a1", "r1"))
        assertTrue(almacen.activa.first())

        almacen.borrar()

        assertNull(almacen.tokens())
        assertFalse(almacen.activa.first())
        assertNull(AlmacenSesion(datos, cifrador).tokens())
    }

    // También cuando el Renovador la borra por un token revocado: el id es de esa cuenta.
    @Test
    fun el_id_del_telefono_vive_y_muere_con_la_sesion() = runBlocking<Unit> {
        val almacen = AlmacenSesion(datos, cifrador)
        almacen.guardarDispositivo(3)
        assertNull(almacen.dispositivo())

        almacen.guardar(tokens("a1", "r1"))
        almacen.guardarDispositivo(3)
        assertEquals(3L, AlmacenSesion(datos, cifrador).dispositivo())

        almacen.borrar()
        assertNull(almacen.dispositivo())
    }

    @Test
    fun abrir_guarda_la_cuenta_y_renovar_no_la_toca() = runBlocking<Unit> {
        val almacen = AlmacenSesion(datos, cifrador)
        almacen.abrir(tokens("a1", "r1"), cuenta = 12)
        almacen.guardarDispositivo(3)

        almacen.guardar(tokens("a2", "r2"))
        assertEquals(12L, AlmacenSesion(datos, cifrador).cuenta())
        assertEquals(3L, almacen.dispositivo())

        // Otra sesión no hereda el teléfono de la anterior.
        almacen.abrir(tokens("b1", "s1"), cuenta = 13)
        assertEquals(13L, almacen.cuenta())
        assertNull(almacen.dispositivo())

        almacen.borrar()
        assertNull(almacen.cuenta())
    }
}
