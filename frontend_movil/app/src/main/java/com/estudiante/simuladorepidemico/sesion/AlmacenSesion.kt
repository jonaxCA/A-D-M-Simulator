package com.estudiante.simuladorepidemico.sesion

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.estudiante.simuladorepidemico.red.Tokens
import com.estudiante.simuladorepidemico.red.json
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

// Los tokens se guardan cifrados; en memoria queda una copia para no descifrar en cada petición.
class AlmacenSesion(private val datos: DataStore<Preferences>, private val cifrador: Cifrador) {
    private val candado = Mutex()
    private var leido = false
    private var actuales: Tokens? = null

    val activa: Flow<Boolean> = datos.data.map { TOKENS in it }

    suspend fun tokens(): Tokens? = candado.withLock {
        if (!leido) {
            actuales = datos.data.first()[TOKENS]?.let(::descifrar)
            leido = true
        }
        actuales
    }

    suspend fun guardar(tokens: Tokens) = candado.withLock {
        datos.edit { it[TOKENS] = cifrador.cifrar(json.encodeToString(tokens)) }
        actuales = tokens
        leido = true
    }

    suspend fun borrar() = candado.withLock {
        datos.edit { it.remove(TOKENS) }
        actuales = null
        leido = true
    }

    // Sin la llave del Keystore (app reinstalada o respaldo restaurado) no hay sesión.
    private fun descifrar(cifrado: String): Tokens? =
        runCatching { json.decodeFromString<Tokens>(cifrador.descifrar(cifrado)) }.getOrNull()

    private companion object {
        val TOKENS = stringPreferencesKey("tokens")
    }
}
