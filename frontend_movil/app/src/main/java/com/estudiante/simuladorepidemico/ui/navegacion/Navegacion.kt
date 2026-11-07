package com.estudiante.simuladorepidemico.ui.navegacion

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.estudiante.simuladorepidemico.Contenedor
import com.estudiante.simuladorepidemico.ui.inicio.PantallaInicio
import com.estudiante.simuladorepidemico.ui.login.LoginViewModel
import com.estudiante.simuladorepidemico.ui.login.PantallaLogin
import com.estudiante.simuladorepidemico.ui.perfil.PantallaPerfil
import com.estudiante.simuladorepidemico.ui.perfil.PerfilViewModel
import kotlinx.serialization.Serializable

@Serializable
object Login

@Serializable
object Inicio

@Serializable
object MiPerfil

@Composable
fun Navegacion(contenedor: Contenedor) {
    val activa by contenedor.sesion.activa.collectAsStateWithLifecycle(initialValue = null)
    val conSesion = activa ?: run {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        return
    }
    val nav = rememberNavController()
    val primera = remember { if (conSesion) Inicio else Login }

    NavHost(navController = nav, startDestination = primera) {
        composable<Login> { PantallaLogin(viewModel { LoginViewModel(contenedor.sesion) }) }
        composable<Inicio> { PantallaInicio(alAbrirPerfil = { nav.navigate(MiPerfil) }) }
        composable<MiPerfil> {
            PantallaPerfil(viewModel { PerfilViewModel(contenedor.sesion) }, alVolver = { nav.popBackStack() })
        }
    }

    // Iniciar, cerrar o perder la sesión (revocada o vencida) cambia de pantalla y vacía la pila:
    // con "atrás" no se regresa al login ni a una pantalla sin sesión.
    LaunchedEffect(conSesion) {
        val destino: Any = if (conSesion) Inicio else Login
        if (nav.currentDestination?.hasRoute(destino::class) != true) {
            nav.navigate(destino) { popUpTo(nav.graph.id) { inclusive = true } }
        }
    }
}
