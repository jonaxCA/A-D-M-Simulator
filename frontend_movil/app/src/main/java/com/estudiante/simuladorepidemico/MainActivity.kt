package com.estudiante.simuladorepidemico

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.estudiante.simuladorepidemico.avisos.ABRIR_AVISOS
import com.estudiante.simuladorepidemico.ui.navegacion.ConIndicadorDeConexion
import com.estudiante.simuladorepidemico.ui.navegacion.ConPermisoRedLocal
import com.estudiante.simuladorepidemico.ui.navegacion.Navegacion
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia

class MainActivity : ComponentActivity() {
    // La notificación de avisos abre la app con ABRIR_AVISOS: la navegación va a esa pantalla.
    private var abrirAvisos by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // La franja de conexión es oscura: los íconos de la barra de estado van en blanco.
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT))
        abrirAvisos = savedInstanceState == null && intent.getBooleanExtra(ABRIR_AVISOS, false)
        val contenedor = (application as EpidemiaApp).contenedor
        setContent {
            TemaEpidemia {
                ConIndicadorDeConexion {
                    ConPermisoRedLocal {
                        Navegacion(contenedor, abrirAvisos = abrirAvisos, alAbrirAvisos = { abrirAvisos = false })
                    }
                }
            }
        }
    }

    // Con la app abierta, la notificación llega aquí (FLAG_ACTIVITY_SINGLE_TOP).
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (intent.getBooleanExtra(ABRIR_AVISOS, false)) abrirAvisos = true
    }
}
