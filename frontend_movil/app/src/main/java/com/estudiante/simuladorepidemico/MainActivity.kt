package com.estudiante.simuladorepidemico

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.estudiante.simuladorepidemico.ui.navegacion.ConPermisoRedLocal
import com.estudiante.simuladorepidemico.ui.navegacion.Navegacion
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val contenedor = (application as EpidemiaApp).contenedor
        setContent {
            TemaEpidemia {
                ConPermisoRedLocal { Navegacion(contenedor) }
            }
        }
    }
}
