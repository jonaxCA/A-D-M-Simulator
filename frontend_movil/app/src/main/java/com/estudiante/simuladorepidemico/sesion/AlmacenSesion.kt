package com.estudiante.simuladorepidemico.sesion

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import com.estudiante.simuladorepidemico.red.Tokens
import com.estudiante.simuladorepidemico.red.json
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

// Los tokens se guardan cifrados; en memoria queda una copia para no descifrar en cada petición.
// Con ellos van el id de la cuenta y el del teléfono en dispositivos, que son de esta sesión y se
// borran con ella. La cuenta se sabe sin red: los casos capturados sin conexión son de ella y solo
// se mandan con una sesión suya.
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

    // Al iniciar sesión, en un solo cambio: nunca quedan los tokens de una cuenta con el id de otra.
    suspend fun abrir(tokens: Tokens, cuenta: Long) = candado.withLock {
        datos.edit {
            it[TOKENS] = cifrador.cifrar(json.encodeToString(tokens))
            it[CUENTA] = cuenta
            it.remove(DISPOSITIVO)
        }
        actuales = tokens
        leido = true
    }

    // Tokens nuevos de la misma sesión (el Renovador): la cuenta y el teléfono se quedan.
    suspend fun guardar(tokens: Tokens) = candado.withLock {
        datos.edit { it[TOKENS] = cifrador.cifrar(json.encodeToString(tokens)) }
        actuales = tokens
        leido = true
    }

    suspend fun cuenta(): Long? = datos.data.first()[CUENTA]

    suspend fun dispositivo(): Long? = datos.data.first()[DISPOSITIVO]

    // Solo con sesión: si se cerró mientras el teléfono se registraba, no queda el id suelto.
    suspend fun guardarDispositivo(id: Long) = candado.withLock {
        datos.edit { if (TOKENS in it) it[DISPOSITIVO] = id }
    }

    suspend fun borrar() = candado.withLock {
        datos.edit {
            it.remove(TOKENS)
            it.remove(CUENTA)
            it.remove(DISPOSITIVO)
        }
        actuales = null
        leido = true
    }

    // Sin la llave del Keystore (app reinstalada o respaldo restaurado) no hay sesión.
    private fun descifrar(cifrado: String): Tokens? =
        runCatching { json.decodeFromString<Tokens>(cifrador.descifrar(cifrado)) }.getOrNull()

    private companion object {
        val TOKENS = stringPreferencesKey("tokens")
        val CUENTA = longPreferencesKey("cuenta")
        val DISPOSITIVO = longPreferencesKey("dispositivo")
    }
}
