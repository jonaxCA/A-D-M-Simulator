package com.estudiante.simuladorepidemico.avisos

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.red.Aviso
import com.estudiante.simuladorepidemico.red.ListaAvisos
import com.estudiante.simuladorepidemico.sesion.Sesion
import kotlinx.coroutines.flow.first

// Los avisos de notificaciones (README, sección 9). No hay push: la app consulta. Para no avisar
// dos veces en el teléfono de lo mismo, se guarda, por cuenta, el id más alto que ya se vio (en la
// pantalla o en una notificación). Los ids crecen: uno nuevo siempre es mayor.
class Avisos(
    private val apis: Apis,
    private val datos: DataStore<Preferences>,
    private val sesion: Sesion,
) {
    // Para la pantalla: los últimos 50, leídos o no. Lo que se ve ya no se vuelve a notificar.
    suspend fun lista(): ListaAvisos {
        val lista = apis.notificaciones().listar(noLeidas = null, limite = LIMITE)
        sesion.cuenta()?.let { marcarVistos(it, lista.avisos) }
        return lista
    }

    suspend fun noLeidos(): Int = apis.notificaciones().listar(noLeidas = true, limite = 1).noLeidas

    suspend fun marcarLeido(id: Long): Aviso = apis.notificaciones().marcarLeido(id)

    // Los no leídos que llegaron desde la última vez, para la notificación del teléfono. Sin sesión,
    // ninguno.
    suspend fun nuevos(): List<Aviso> {
        val cuenta = sesion.cuenta() ?: return emptyList()
        val visto = datos.data.first()[llave(cuenta)] ?: 0L
        val noLeidos = apis.notificaciones().listar(noLeidas = true, limite = LIMITE).avisos
        marcarVistos(cuenta, noLeidos)
        return noLeidos.filter { it.id > visto }
    }

    private suspend fun marcarVistos(cuenta: Long, avisos: List<Aviso>) {
        val mayor = avisos.maxOfOrNull { it.id } ?: return
        datos.edit { it[llave(cuenta)] = maxOf(it[llave(cuenta)] ?: 0L, mayor) }
    }

    private fun llave(cuenta: Long) = longPreferencesKey("aviso_visto_$cuenta")

    private companion object {
        const val LIMITE = 50
    }
}
