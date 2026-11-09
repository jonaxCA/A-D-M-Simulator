package com.estudiante.simuladorepidemico.avisos

import android.Manifest
import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationChannelCompat
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.estudiante.simuladorepidemico.MainActivity
import com.estudiante.simuladorepidemico.R
import com.estudiante.simuladorepidemico.red.Aviso

// Con este extra, MainActivity abre la pantalla de avisos (al tocar la notificación).
const val ABRIR_AVISOS = "abrir_avisos"

// La notificación del teléfono cuando llegan avisos nuevos. Una sola, que se reemplaza: varios
// avisos salen como "N avisos nuevos" con sus títulos. En la pantalla bloqueada no se ve el
// contenido, solo que hay avisos.
class Notificador(private val contexto: Context) {
    private val gestor = NotificationManagerCompat.from(contexto)

    // Desde Android 13 hace falta el permiso; antes, que no las hayan apagado en Ajustes.
    fun puede(): Boolean = gestor.areNotificationsEnabled() &&
        (Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(contexto, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED)

    @SuppressLint("MissingPermission")
    fun mostrar(avisos: List<Aviso>) {
        if (avisos.isEmpty() || !puede()) return
        gestor.createNotificationChannel(
            NotificationChannelCompat.Builder(CANAL, NotificationManagerCompat.IMPORTANCE_DEFAULT)
                .setName("Avisos")
                .setDescription("Corridas terminadas, versiones aprobadas y avisos del sistema.")
                .build()
        )
        val abrir = PendingIntent.getActivity(
            contexto, 0,
            Intent(contexto, MainActivity::class.java)
                .putExtra(ABRIR_AVISOS, true)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val publica = NotificationCompat.Builder(contexto, CANAL)
            .setSmallIcon(R.drawable.ic_aviso)
            .setContentTitle("Tienes avisos nuevos")
            .build()
        val uno = avisos.size == 1
        val notificacion = NotificationCompat.Builder(contexto, CANAL)
            .setSmallIcon(R.drawable.ic_aviso)
            .setContentTitle(if (uno) avisos[0].titulo else "${avisos.size} avisos nuevos")
            .setContentText(if (uno) avisos[0].cuerpo.orEmpty() else avisos.joinToString(" · ") { it.titulo })
            .setStyle(
                if (uno) NotificationCompat.BigTextStyle().bigText(avisos[0].cuerpo.orEmpty())
                else NotificationCompat.InboxStyle().also { estilo -> avisos.take(5).forEach { estilo.addLine(it.titulo) } }
            )
            .setContentIntent(abrir)
            .setAutoCancel(true)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .setPublicVersion(publica)
            .build()
        gestor.notify(ID, notificacion)
    }

    companion object {
        const val CANAL = "avisos"
        const val ID = 1
    }
}
