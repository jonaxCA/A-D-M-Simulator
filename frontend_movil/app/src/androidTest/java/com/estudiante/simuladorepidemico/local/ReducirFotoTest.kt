package com.estudiante.simuladorepidemico.local

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.media.ExifInterface
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.IOException

// Con Bitmap de verdad: en la PC no existe.
@RunWith(AndroidJUnit4::class)
class ReducirFotoTest {
    private val carpeta = File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir, "reducir").apply { mkdirs() }

    @After
    fun borrar() {
        carpeta.deleteRecursively()
    }

    // Una "foto de cámara": JPEG de 4000 × 3000, de lado (EXIF 6) y con su ubicación en el EXIF.
    private fun fotoDeCamara(): File {
        val archivo = File(carpeta, "camara.jpg")
        val imagen = Bitmap.createBitmap(4000, 3000, Bitmap.Config.ARGB_8888).apply { eraseColor(Color.rgb(200, 80, 40)) }
        archivo.outputStream().use { imagen.compress(Bitmap.CompressFormat.JPEG, 90, it) }
        imagen.recycle()
        ExifInterface(archivo.path).apply {
            setAttribute(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_ROTATE_90.toString())
            setAttribute(ExifInterface.TAG_GPS_LATITUDE, "25/1,41/1,11/1")
            setAttribute(ExifInterface.TAG_GPS_LATITUDE_REF, "N")
            saveAttributes()
        }
        return archivo
    }

    @Test
    fun queda_de_1600_derecha_y_sin_la_ubicacion_del_archivo() {
        val original = fotoDeCamara()
        val reducida = File(carpeta, "reducida.jpg")

        reducirFoto({ original.inputStream() }, reducida)

        val limites = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(reducida.path, limites)
        // Venía de lado: la reducida ya está vertical.
        assertEquals(1200 to 1600, limites.outWidth to limites.outHeight)
        assertEquals("image/jpeg", limites.outMimeType)
        val exif = ExifInterface(reducida.path)
        assertNull(exif.getAttribute(ExifInterface.TAG_GPS_LATITUDE))
        assertTrue(reducida.length() < original.length())
    }

    @Test
    fun una_chica_no_se_agranda() {
        val chica = File(carpeta, "chica.png")
        chica.outputStream().use { Bitmap.createBitmap(640, 480, Bitmap.Config.ARGB_8888).compress(Bitmap.CompressFormat.PNG, 100, it) }
        val reducida = File(carpeta, "reducida.jpg")

        reducirFoto({ chica.inputStream() }, reducida)

        val limites = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(reducida.path, limites)
        assertEquals(640 to 480, limites.outWidth to limites.outHeight)
        assertEquals("image/jpeg", limites.outMimeType)
    }

    @Test
    fun lo_que_no_es_imagen_se_rechaza() {
        val texto = File(carpeta, "nota.txt").apply { writeText("no es una foto") }

        assertThrows(IOException::class.java) { reducirFoto({ texto.inputStream() }, File(carpeta, "x.jpg")) }
    }
}
