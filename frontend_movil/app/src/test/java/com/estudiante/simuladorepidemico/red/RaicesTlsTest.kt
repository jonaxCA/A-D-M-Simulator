package com.estudiante.simuladorepidemico.red

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.w3c.dom.Element
import java.io.File
import java.security.MessageDigest
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import javax.xml.parsers.DocumentBuilderFactory

/**
 * D26: la app trae la raíz de Let's Encrypt porque Android 7.0 (minSdk 24) no la incluye de
 * fábrica. Debug reemplaza la configuración de red de release, así que las dos deben confiar en
 * ella; si alguien la quita de una, Android 7.0 deja de conectar sin que nada más falle.
 */
class RaicesTlsTest {
    @Test
    fun la_raiz_es_isrg_root_x1_y_sigue_vigente() {
        val raiz = File("src/main/res/raw/isrg_root_x1.crt").inputStream().use {
            CertificateFactory.getInstance("X.509").generateCertificate(it) as X509Certificate
        }

        assertEquals("CN=ISRG Root X1,O=Internet Security Research Group,C=US", raiz.subjectX500Principal.name)
        val huella = MessageDigest.getInstance("SHA-256").digest(raiz.encoded).joinToString("") { "%02X".format(it) }
        assertEquals(HUELLA_ISRG_ROOT_X1, huella)
        raiz.checkValidity()
    }

    @Test
    fun release_y_debug_confian_en_el_sistema_y_en_la_raiz() {
        val casos = listOf(
            "src/main/res/xml/network_security_config.xml" to "false",
            "src/debug/res/xml/network_security_config.xml" to "true",
        )
        for ((archivo, http) in casos) {
            val documento = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(File(archivo))
            val base = documento.getElementsByTagName("base-config").item(0) as Element
            assertEquals(archivo, http, base.getAttribute("cleartextTrafficPermitted"))
            val certificados = base.getElementsByTagName("certificates")
            val fuentes = (0 until certificados.length).map { (certificados.item(it) as Element).getAttribute("src") }
            assertEquals(archivo, listOf("system", "@raw/isrg_root_x1"), fuentes)
        }
    }

    @Test
    fun el_manifiesto_usa_la_configuracion() {
        val manifiesto = File("src/main/AndroidManifest.xml").readText()
        assertTrue(manifiesto.contains("android:networkSecurityConfig=\"@xml/network_security_config\""))
    }

    private companion object {
        // La huella publicada por Let's Encrypt (letsencrypt.org/certificates).
        const val HUELLA_ISRG_ROOT_X1 = "96BCEC06264976F37460779ACF28C5A7CFE8A3C0AAE11A8FFCEE05C0BDDF08C6"
    }
}
