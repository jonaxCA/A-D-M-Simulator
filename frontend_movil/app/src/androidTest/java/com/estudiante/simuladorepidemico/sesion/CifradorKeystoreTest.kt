package com.estudiante.simuladorepidemico.sesion

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CifradorKeystoreTest {
    @Test
    fun cifra_con_iv_nuevo_y_otra_instancia_descifra() {
        val texto = """{"access_token":"a1","refresh_token":"r1"}"""
        val uno = CifradorKeystore("epidemia_prueba").cifrar(texto)
        val dos = CifradorKeystore("epidemia_prueba").cifrar(texto)

        assertNotEquals(uno, dos)
        assertEquals(texto, CifradorKeystore("epidemia_prueba").descifrar(uno))
        assertEquals(texto, CifradorKeystore("epidemia_prueba").descifrar(dos))
    }
}
