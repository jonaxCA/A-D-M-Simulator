package com.estudiante.simuladorepidemico.avisos

import android.Manifest
import android.app.Notification
import android.app.NotificationManager
import android.os.Build
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.estudiante.simuladorepidemico.red.Aviso
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

// La notificación de verdad, en el sistema del emulador.
@RunWith(AndroidJUnit4::class)
class NotificadorTest {
    private val instrumentacion = InstrumentationRegistry.getInstrumentation()
    private val contexto = instrumentacion.targetContext
    private val sistema = contexto.getSystemService(NotificationManager::class.java)

    @Before
    fun permiso() {
        if (Build.VERSION.SDK_INT >= 33) {
            instrumentacion.uiAutomation.grantRuntimePermission(contexto.packageName, Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    @After
    fun limpiar() = sistema.cancelAll()

    private fun aviso(id: Long, titulo: String) = Aviso(id, "RUN_FINISHED", titulo, "Brote de influenza en Monterrey.", null, "2026-11-07T15:02:00+00:00")

    // El sistema las publica aparte: se espera un poco a que aparezca.
    private fun mostrada(): Notification {
        val fin = System.currentTimeMillis() + 5_000
        while (true) {
            sistema.activeNotifications.firstOrNull { it.id == Notificador.ID }?.let { return it.notification }
            check(System.currentTimeMillis() < fin) { "La notificación no apareció." }
            Thread.sleep(100)
        }
    }

    @Test
    fun varios_avisos_salen_en_una_notificacion_que_no_se_lee_bloqueado() {
        val notificador = Notificador(contexto)
        assertTrue(notificador.puede())

        notificador.mostrar(listOf(aviso(8, "Otra corrida"), aviso(7, "La corrida SIM-00042 terminó")))

        val notificacion = mostrada()
        assertEquals("2 avisos nuevos", notificacion.extras.getString(Notification.EXTRA_TITLE))
        assertEquals(Notification.VISIBILITY_PRIVATE, notificacion.visibility)
        assertEquals("Tienes avisos nuevos", notificacion.publicVersion.extras.getString(Notification.EXTRA_TITLE))
        assertNotNull(notificacion.contentIntent)
        assertEquals(Notificador.CANAL, notificacion.channelId)
    }

    @Test
    fun uno_solo_lleva_su_titulo_y_su_texto() {
        Notificador(contexto).mostrar(listOf(aviso(7, "La corrida SIM-00042 terminó")))

        val notificacion = mostrada()
        assertEquals("La corrida SIM-00042 terminó", notificacion.extras.getString(Notification.EXTRA_TITLE))
        assertEquals("Brote de influenza en Monterrey.", notificacion.extras.getCharSequence(Notification.EXTRA_TEXT).toString())
    }

    @Test
    fun sin_avisos_no_muestra_nada() {
        Notificador(contexto).mostrar(emptyList())

        assertTrue(sistema.activeNotifications.none { it.id == Notificador.ID })
    }
}
