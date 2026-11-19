package com.estudiante.simuladorepidemico.sesion

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

interface Cifrador {
    fun cifrar(texto: String): String
    fun descifrar(cifrado: String): String
}

// AES-GCM con una llave que vive en el Keystore de Android y nunca sale de él.
class CifradorKeystore(private val alias: String = "epidemia_sesion") : Cifrador {
    private val llave: SecretKey by lazy {
        val almacen = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        almacen.getKey(alias, null) as SecretKey? ?: KeyGenerator
            .getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
            .apply {
                init(
                    KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                        .build()
                )
            }
            .generateKey()
    }

    override fun cifrar(texto: String): String {
        val cifra = Cipher.getInstance(TRANSFORMACION).apply { init(Cipher.ENCRYPT_MODE, llave) }
        return Base64.encodeToString(cifra.iv + cifra.doFinal(texto.toByteArray()), Base64.NO_WRAP)
    }

    override fun descifrar(cifrado: String): String {
        val bytes = Base64.decode(cifrado, Base64.NO_WRAP)
        val cifra = Cipher.getInstance(TRANSFORMACION)
        cifra.init(Cipher.DECRYPT_MODE, llave, GCMParameterSpec(128, bytes, 0, IV))
        return String(cifra.doFinal(bytes, IV, bytes.size - IV))
    }

    private companion object {
        const val TRANSFORMACION = "AES/GCM/NoPadding"
        const val IV = 12
    }
}
