package com.estudiante.simuladorepidemico.ui.vacunas

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.TimeUnit

// ML Kit de verdad con el mismo lector que la cámara. qr_lote.png (en los assets de estas pruebas)
// es un QR con "EPI-QR-2026-001", hecho con el codificador de TCPDF.
@RunWith(AndroidJUnit4::class)
class LectorDeLotesTest {
    private fun imagen(): Bitmap = InstrumentationRegistry.getInstrumentation().context.assets
        .open("qr_lote.png").use(BitmapFactory::decodeStream)

    private fun leer(bitmap: Bitmap, giro: Int = 0): List<String> {
        val lector = lectorDeLotes()
        try {
            return Tasks.await(lector.process(InputImage.fromBitmap(bitmap, giro)), 10, TimeUnit.SECONDS).mapNotNull { it.rawValue }
        } finally {
            lector.close()
        }
    }

    @Test
    fun lee_el_qr_de_un_lote() {
        assertEquals(listOf("EPI-QR-2026-001"), leer(imagen()))
    }

    @Test
    fun lee_el_qr_aunque_el_telefono_este_girado() {
        assertEquals(listOf("EPI-QR-2026-001"), leer(imagen(), giro = 90))
    }

    @Test
    fun en_una_imagen_sin_codigo_no_lee_nada() {
        val blanca = Bitmap.createBitmap(232, 232, Bitmap.Config.ARGB_8888).apply { eraseColor(android.graphics.Color.WHITE) }
        assertEquals(emptyList<String>(), leer(blanca))
    }
}
