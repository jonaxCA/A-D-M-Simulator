package com.estudiante.simuladorepidemico

import android.app.Application
import android.content.Context
import androidx.datastore.preferences.preferencesDataStore
import androidx.room.Room
import com.estudiante.simuladorepidemico.local.BaseLocal
import com.estudiante.simuladorepidemico.local.Fotos
import com.estudiante.simuladorepidemico.sesion.CifradorKeystore
import com.estudiante.simuladorepidemico.sesion.esteTelefono
import com.estudiante.simuladorepidemico.trabajos.TrabajoAvisos
import com.estudiante.simuladorepidemico.trabajos.TrabajoSincronizar
import com.estudiante.simuladorepidemico.ubicacion.UbicadorFused
import java.io.File

// Fuera de los respaldos (res/xml): la llave del Keystore y los device_uid no viajan con ellos.
private val Context.datosSesion by preferencesDataStore(name = "sesion")

// filesDir/fotos: también fuera de los respaldos. res/xml/rutas_fotos.xml deja que la app de
// cámara escriba en fotos/camara/.
const val CARPETA_FOTOS = "fotos"

class EpidemiaApp : Application() {
    val contenedor by lazy {
        val base = Room.databaseBuilder(this, BaseLocal::class.java, BaseLocal.ARCHIVO).build()
        Contenedor(
            datos = datosSesion,
            cifrador = CifradorKeystore(),
            directorioUrl = BuildConfig.DIRECTORIO,
            telefono = esteTelefono(BuildConfig.VERSION_NAME),
            casos = base.casos(),
            catalogo = base.catalogo(),
            programarEnvio = { TrabajoSincronizar.programar(this) },
            ubicador = UbicadorFused(this),
            fotos = Fotos(File(filesDir, CARPETA_FOTOS)),
            programarAvisos = { TrabajoAvisos.programar(this) },
        )
    }
}
