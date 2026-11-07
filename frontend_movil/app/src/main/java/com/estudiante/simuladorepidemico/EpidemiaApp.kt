package com.estudiante.simuladorepidemico

import android.app.Application
import android.content.Context
import androidx.datastore.preferences.preferencesDataStore
import com.estudiante.simuladorepidemico.sesion.CifradorKeystore
import com.estudiante.simuladorepidemico.sesion.esteTelefono

// Fuera de los respaldos (res/xml): la llave del Keystore y los device_uid no viajan con ellos.
private val Context.datosSesion by preferencesDataStore(name = "sesion")

class EpidemiaApp : Application() {
    val contenedor by lazy {
        Contenedor(datosSesion, CifradorKeystore(), BuildConfig.DIRECTORIO, esteTelefono(BuildConfig.VERSION_NAME))
    }
}
