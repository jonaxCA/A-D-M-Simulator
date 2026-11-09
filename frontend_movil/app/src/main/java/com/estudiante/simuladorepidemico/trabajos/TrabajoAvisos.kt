package com.estudiante.simuladorepidemico.trabajos

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.estudiante.simuladorepidemico.EpidemiaApp
import com.estudiante.simuladorepidemico.avisos.Notificador
import kotlinx.coroutines.CancellationException
import java.util.concurrent.TimeUnit

// No hay notificaciones push (README, sección 9): cada 15 minutos con red, que es lo menos que deja
// WorkManager, se consultan los avisos nuevos y, si hay, se muestra la notificación.
class TrabajoAvisos(contexto: Context, parametros: WorkerParameters) : CoroutineWorker(contexto, parametros) {
    override suspend fun doWork(): Result {
        val app = applicationContext as EpidemiaApp
        return try {
            Notificador(app).mostrar(app.contenedor.avisos.nuevos())
            Result.success()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            // Sin red o sin sesión: la siguiente vuelta lo intenta otra vez.
            Result.success()
        }
    }

    companion object {
        private const val NOMBRE = "consultar-avisos"

        // KEEP: programarlo cada vez que se llega al inicio no reinicia la cuenta de los 15 minutos.
        fun programar(contexto: Context) {
            val pedido = PeriodicWorkRequestBuilder<TrabajoAvisos>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(contexto).enqueueUniquePeriodicWork(NOMBRE, ExistingPeriodicWorkPolicy.KEEP, pedido)
        }
    }
}
