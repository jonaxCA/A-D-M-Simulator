package com.estudiante.simuladorepidemico.local

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.util.UUID

// Los archivos de las fotos, en el almacenamiento privado de la app (filesDir/fotos, fuera de los
// respaldos). Mientras el caso no se guarda son borradores; al guardarlo pasan a fotos/<id>.jpg y,
// ya subidas a evidencias, se borran.
class Fotos(
    private val carpeta: File,
    private val reducir: (abrir: () -> InputStream, destino: File) -> Unit = ::reducirFoto,
) {
    private val borradores = File(carpeta, "borrador")
    private val camara = File(carpeta, "camara")

    // Donde la app de cámara deja la foto completa; importar() la reduce y se borra.
    fun paraLaCamara(): File {
        camara.mkdirs()
        return File(camara, "${UUID.randomUUID()}.jpg")
    }

    // Reduce la imagen y la deja como borrador del formulario. Devuelve su id.
    suspend fun importar(abrir: () -> InputStream): String = withContext(Dispatchers.IO) {
        val id = UUID.randomUUID().toString()
        borradores.mkdirs()
        val destino = File(borradores, "$id.jpg")
        try {
            reducir(abrir, destino)
        } catch (e: Exception) {
            destino.delete()
            throw e
        }
        id
    }

    // El caso se guarda: sus fotos dejan de ser borradores. Si una ya se había movido (un intento
    // anterior que falló después), se deja como está.
    fun confirmar(ids: List<String>) {
        ids.forEach { id ->
            val borrador = File(borradores, "$id.jpg")
            if (borrador.exists() && !borrador.renameTo(archivo(id))) throw IOException("No se pudo guardar la foto.")
            if (!archivo(id).exists()) throw IOException("La foto ya no está en el teléfono.")
        }
    }

    fun archivo(id: String) = File(carpeta, "$id.jpg")

    // La que se ve en el formulario: borrador o ya guardada.
    fun vista(id: String): File = File(borradores, "$id.jpg").takeIf { it.exists() } ?: archivo(id)

    fun borrar(ids: Collection<String>) {
        ids.forEach {
            File(borradores, "$it.jpg").delete()
            archivo(it).delete()
        }
    }

    // Lo que quedó de un formulario que no se guardó (la app se cerró a medias).
    fun limpiarBorradores() {
        borradores.listFiles()?.forEach { it.delete() }
        camara.listFiles()?.forEach { it.delete() }
    }
}

const val LADO_MAXIMO = 1600

// A LADO_MAXIMO px por lado, derecha según su EXIF y en JPEG. El JPEG nuevo no lleva EXIF: se va
// también la ubicación GPS que algunas cámaras guardan dentro de la foto.
fun reducirFoto(abrir: () -> InputStream, destino: File) {
    val limites = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    abrir().use { BitmapFactory.decodeStream(it, null, limites) }
    if (limites.outWidth <= 0 || limites.outHeight <= 0) throw IOException("El archivo no es una imagen.")
    var muestra = 1
    while (maxOf(limites.outWidth, limites.outHeight) / (muestra * 2) >= LADO_MAXIMO) muestra *= 2
    val leida = abrir().use { BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = muestra }) }
        ?: throw IOException("No se pudo leer la imagen.")
    val giro = runCatching {
        when (abrir().use { ExifInterface(it) }.getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
            ExifInterface.ORIENTATION_ROTATE_90 -> 90f
            ExifInterface.ORIENTATION_ROTATE_180 -> 180f
            ExifInterface.ORIENTATION_ROTATE_270 -> 270f
            else -> 0f
        }
    }.getOrDefault(0f)
    val escala = minOf(1f, LADO_MAXIMO.toFloat() / maxOf(leida.width, leida.height))
    val matriz = Matrix().apply {
        postScale(escala, escala)
        postRotate(giro)
    }
    val lista = Bitmap.createBitmap(leida, 0, 0, leida.width, leida.height, matriz, true)
    destino.outputStream().use { lista.compress(Bitmap.CompressFormat.JPEG, 85, it) }
    if (lista !== leida) lista.recycle()
    leida.recycle()
}
