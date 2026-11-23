package com.estudiante.simuladorepidemico.ui.navegacion

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.toRoute
import com.estudiante.simuladorepidemico.Contenedor
import com.estudiante.simuladorepidemico.ui.avisos.AvisosViewModel
import com.estudiante.simuladorepidemico.ui.avisos.PantallaAvisos
import com.estudiante.simuladorepidemico.ui.casos.CapturaViewModel
import com.estudiante.simuladorepidemico.ui.casos.MisCasosViewModel
import com.estudiante.simuladorepidemico.ui.casos.PantallaCaptura
import com.estudiante.simuladorepidemico.ui.casos.PantallaMisCasos
import com.estudiante.simuladorepidemico.ui.casos.PantallaSeguimiento
import com.estudiante.simuladorepidemico.ui.casos.SeguimientoViewModel
import com.estudiante.simuladorepidemico.ui.consulta.ConsultaViewModel
import com.estudiante.simuladorepidemico.ui.consulta.PantallaConsulta
import com.estudiante.simuladorepidemico.ui.inicio.InicioViewModel
import com.estudiante.simuladorepidemico.ui.inicio.PantallaInicio
import com.estudiante.simuladorepidemico.ui.login.LoginViewModel
import com.estudiante.simuladorepidemico.ui.login.PantallaLogin
import com.estudiante.simuladorepidemico.ui.perfil.PantallaPerfil
import com.estudiante.simuladorepidemico.ui.perfil.PerfilViewModel
import com.estudiante.simuladorepidemico.ui.vacunas.PantallaVacunas
import com.estudiante.simuladorepidemico.ui.vacunas.VacunasViewModel
import kotlinx.serialization.Serializable

@Serializable
object Login

@Serializable
object Inicio

@Serializable
object MiPerfil

@Serializable
object Captura

@Serializable
object MisCasos

@Serializable
object Vacunas

@Serializable
object Avisos

@Serializable
data class Seguimiento(val caso: Long)

@Serializable
object Consulta

@Composable
fun Navegacion(contenedor: Contenedor, abrirAvisos: Boolean = false, alAbrirAvisos: () -> Unit = {}) {
    val activa by contenedor.sesion.activa.collectAsStateWithLifecycle(initialValue = null)
    val conSesion = activa ?: run {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        return
    }
    val nav = rememberNavController()
    val primera = remember { if (conSesion) Inicio else Login }
    var sesionTerminada by rememberSaveable { mutableStateOf(false) }

    // Al cambiar de sesión se vacía la pila: con "atrás" no se regresa al login ni a una pantalla
    // sin sesión.
    fun soloEn(destino: Any) = nav.navigate(destino) { popUpTo(nav.graph.id) { inclusive = true } }

    NavHost(navController = nav, startDestination = primera) {
        composable<Login> {
            PantallaLogin(
                viewModel { LoginViewModel(contenedor.sesion) }, alQuedarDentro = { soloEn(Inicio) },
                sesionTerminada = sesionTerminada,
            )
        }
        composable<Inicio> {
            PantallaInicio(
                viewModel {
                    InicioViewModel(
                        contenedor.sesion, contenedor.casos, contenedor.catalogos, contenedor.avisos, contenedor.apis,
                        contenedor.catalogo, contenedor.programarEnvio, contenedor.programarAvisos,
                    )
                },
                alCapturar = { nav.navigate(Captura) },
                alVerCasos = { nav.navigate(MisCasos) },
                alVerLotes = { nav.navigate(Vacunas) },
                alVerAvisos = { nav.navigate(Avisos) },
                alAbrirPerfil = { nav.navigate(MiPerfil) },
                alConsultar = { nav.navigate(Consulta) },
            )
        }
        composable<Captura> {
            PantallaCaptura(
                viewModel {
                    CapturaViewModel(
                        contenedor.sesion, contenedor.casos, contenedor.catalogo, contenedor.catalogos,
                        contenedor.programarEnvio, contenedor.ubicador, contenedor.fotos, contenedor.cifrador,
                    )
                },
                alVolver = { nav.popBackStack() },
            )
        }
        composable<MisCasos> {
            PantallaMisCasos(
                viewModel {
                    MisCasosViewModel(
                        contenedor.sesion, contenedor.apis, contenedor.casos, contenedor.catalogo, contenedor.fotos,
                        contenedor.programarEnvio,
                    )
                },
                alVolver = { nav.popBackStack() },
                alAbrir = { nav.navigate(Seguimiento(it)) },
            )
        }
        composable<Seguimiento> { entrada ->
            val caso = entrada.toRoute<Seguimiento>().caso
            PantallaSeguimiento(
                viewModel { SeguimientoViewModel(contenedor.apis, contenedor.sesion, caso) },
                alVolver = { nav.popBackStack() },
            )
        }
        composable<Consulta> {
            PantallaConsulta(viewModel { ConsultaViewModel(contenedor.apis, contenedor.catalogo) }, alVolver = { nav.popBackStack() })
        }
        composable<Vacunas> {
            PantallaVacunas(viewModel { VacunasViewModel(contenedor.apis, contenedor.catalogo) }, alVolver = { nav.popBackStack() })
        }
        composable<Avisos> {
            PantallaAvisos(viewModel { AvisosViewModel(contenedor.avisos) }, alVolver = { nav.popBackStack() })
        }
        composable<MiPerfil> {
            PantallaPerfil(
                viewModel { PerfilViewModel(contenedor.sesion, contenedor.casos) },
                alVolver = { nav.popBackStack() },
            )
        }
    }

    // Cerrar o perder la sesión (revocada o vencida) regresa al login desde cualquier pantalla.
    // Al iniciarla, el login pasa al inicio por su cuenta, cuando también registró el teléfono.
    LaunchedEffect(conSesion) {
        if (!conSesion && nav.currentDestination?.hasRoute(Login::class) != true) {
            sesionTerminada = true
            soloEn(Login)
        }
        if (conSesion) sesionTerminada = false
    }

    // Al tocar la notificación de avisos. Sin sesión se queda en el login: los avisos son de la cuenta.
    LaunchedEffect(abrirAvisos, conSesion) {
        if (abrirAvisos && conSesion) {
            if (nav.currentDestination?.hasRoute(Avisos::class) != true) nav.navigate(Avisos)
            alAbrirAvisos()
        }
    }
}
