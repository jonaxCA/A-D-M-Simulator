package com.estudiante.simuladorepidemico.sesion

import android.os.Build
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.red.PedidoDispositivo
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import retrofit2.HttpException
import java.util.UUID

// Lo que dispositivos guarda del teléfono además de su device_uid.
data class DescripcionTelefono(val modelo: String, val version: String)

// El modelo como lo conoce la gente ("Google Pixel 7") y la versión de la app, en los largos que
// acepta dispositivos.
fun esteTelefono(version: String): DescripcionTelefono {
    val modelo = if (Build.MODEL.startsWith(Build.MANUFACTURER, ignoreCase = true)) Build.MODEL
    else "${Build.MANUFACTURER} ${Build.MODEL}"
    return DescripcionTelefono(modelo.take(80), version.take(20))
}

// Registra el teléfono en dispositivos con un device_uid por cuenta: un device_uid no puede ser de
// dos cuentas, así que en un teléfono compartido cada cuenta tiene el suyo, en lugar de un registro
// nuevo cada vez que cambia quien entra. Los uid viven en el DataStore de la sesión, que no entra
// en los respaldos: restaurados en otro teléfono, serían los de este.
class Telefono(
    private val datos: DataStore<Preferences>,
    private val apis: Apis,
    private val descripcion: DescripcionTelefono,
) {
    private val candado = Mutex()

    // Devuelve el id del registro: el device_id de los casos. Con otroSiChoca, un 409 (el uid está
    // revocado o es de otra cuenta) se resuelve una sola vez con un uid nuevo; sin él, se lanza.
    suspend fun registrar(cuenta: Long, otroSiChoca: Boolean): Long = candado.withLock {
        try {
            enviar(uid(cuenta) ?: nuevoUid(cuenta))
        } catch (e: HttpException) {
            if (e.code() != 409 || !otroSiChoca) throw e
            enviar(nuevoUid(cuenta))
        }
    }

    private suspend fun enviar(uid: String): Long = apis.dispositivos()
        .registrar(PedidoDispositivo(uid, "android", descripcion.modelo, descripcion.version)).id

    private suspend fun uid(cuenta: Long): String? = datos.data.first()[llave(cuenta)]

    // Se guarda antes de mandarlo: si no hay red, el siguiente intento usa el mismo.
    private suspend fun nuevoUid(cuenta: Long): String {
        val uid = UUID.randomUUID().toString()
        datos.edit { it[llave(cuenta)] = uid }
        return uid
    }

    private fun llave(cuenta: Long) = stringPreferencesKey("device_uid_$cuenta")
}
