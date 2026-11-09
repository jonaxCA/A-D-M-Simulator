package com.estudiante.simuladorepidemico.trabajos

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.estudiante.simuladorepidemico.EpidemiaApp
import java.util.concurrent.TimeUnit

// Corre el Sincronizador cuando hay red, aunque la app esté cerrada; si falla, WorkManager lo
// reintenta cada vez más espaciado.
class TrabajoSincronizar(contexto: Context, parametros: WorkerParameters) : CoroutineWorker(contexto, parametros) {
    override suspend fun doWork(): Result =
        when ((applicationContext as EpidemiaApp).contenedor.sincronizador.enviar()) {
            Envio.LISTO, Envio.SIN_SESION -> Result.success()
            Envio.REINTENTAR -> Result.retry()
        }

    companion object {
        private const val NOMBRE = "sincronizar-casos"

        // APPEND_OR_REPLACE: un caso capturado mientras otra corrida termina no se queda esperando
        // a la siguiente; corre otra al acabar esa.
        fun programar(contexto: Context) {
            val pedido = OneTimeWorkRequestBuilder<TrabajoSincronizar>()
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(contexto).enqueueUniqueWork(NOMBRE, ExistingWorkPolicy.APPEND_OR_REPLACE, pedido)
        }
    }
}
