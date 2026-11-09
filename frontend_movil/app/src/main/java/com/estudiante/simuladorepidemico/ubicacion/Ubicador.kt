package com.estudiante.simuladorepidemico.ubicacion

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.location.LocationManager
import androidx.core.location.LocationManagerCompat
import com.google.android.gms.location.CurrentLocationRequest
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.math.roundToLong

// precisionMetros: el radio en que está el punto (68 % de probabilidad), si el teléfono lo da.
data class Ubicacion(val latitud: Double, val longitud: Double, val precisionMetros: Float? = null)

sealed interface Lectura {
    data class Lista(val ubicacion: Ubicacion) : Lectura

    // La ubicación del teléfono está desactivada.
    data object Apagada : Lectura

    // No llegó una lectura a tiempo (sin cielo abierto, el GPS tarda).
    data object SinSenal : Lectura
}

fun interface Ubicador {
    // Quien la llama ya tiene permiso de ubicación: precisa, el fino; si no, el aproximado.
    suspend fun leer(precisa: Boolean): Lectura
}

// cases guarda NUMERIC(9,6): seis decimales, unos 11 cm.
fun aSeisDecimales(grados: Double): Double = (grados * 1_000_000).roundToLong() / 1_000_000.0

// Con Google Play services. Sin red funciona con el GPS: por eso espera hasta 30 s.
class UbicadorFused(private val contexto: Context) : Ubicador {
    private val cliente = LocationServices.getFusedLocationProviderClient(contexto)

    @SuppressLint("MissingPermission")
    override suspend fun leer(precisa: Boolean): Lectura {
        val gestor = contexto.getSystemService(LocationManager::class.java)
        if (gestor == null || !LocationManagerCompat.isLocationEnabled(gestor)) return Lectura.Apagada
        val pedido = CurrentLocationRequest.Builder()
            .setPriority(if (precisa) Priority.PRIORITY_HIGH_ACCURACY else Priority.PRIORITY_BALANCED_POWER_ACCURACY)
            // Una lectura de hace menos de un minuto sirve: el caso se captura donde está la persona.
            .setMaxUpdateAgeMillis(60_000)
            .setDurationMillis(30_000)
            .build()
        val cancelar = CancellationTokenSource()
        val lugar = suspendCancellableCoroutine<Location?> { continuacion ->
            cliente.getCurrentLocation(pedido, cancelar.token)
                .addOnSuccessListener { continuacion.resume(it) }
                .addOnFailureListener { continuacion.resume(null) }
            continuacion.invokeOnCancellation { cancelar.cancel() }
        }
        return lugar?.let {
            Lectura.Lista(
                Ubicacion(aSeisDecimales(it.latitude), aSeisDecimales(it.longitude), it.accuracy.takeIf { _ -> it.hasAccuracy() })
            )
        } ?: Lectura.SinSenal
    }
}
