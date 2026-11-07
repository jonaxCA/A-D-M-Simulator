package com.estudiante.simuladorepidemico.ui.casos

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.local.CasoLocal
import com.estudiante.simuladorepidemico.local.CasosDao
import com.estudiante.simuladorepidemico.local.CatalogoDao
import com.estudiante.simuladorepidemico.local.Catalogos
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.local.Municipio
import com.estudiante.simuladorepidemico.red.mensajeDeError
import com.estudiante.simuladorepidemico.sesion.Sesion
import com.estudiante.simuladorepidemico.ubicacion.Lectura
import com.estudiante.simuladorepidemico.ubicacion.Ubicacion
import com.estudiante.simuladorepidemico.ubicacion.Ubicador
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.util.UUID

data class EstadoCaptura(
    val fechaReporte: LocalDate,
    val enfermedades: List<Enfermedad> = emptyList(),
    val municipios: List<Municipio> = emptyList(),
    val enfermedad: Long? = null,
    val municipio: Long? = null,
    val inicioSintomas: LocalDate? = null,
    val edad: String = "",
    val sexo: String? = null,
    val resultadoPrueba: String? = null,
    val severidad: String? = null,
    val errores: List<String> = emptyList(),
    val guardando: Boolean = false,
    val guardados: Int = 0,
    val descargando: Boolean = false,
    val errorCatalogos: String? = null,
    val ubicacion: Ubicacion? = null,
    val ubicando: Boolean = false,
    val errorUbicacion: String? = null,
    val sinPermisoDeUbicacion: Boolean = false,
) {
    val sinCatalogos: Boolean
        get() = enfermedades.isEmpty() || municipios.isEmpty()
}

// Las mismas reglas que casos (backend_web/queries.py, valida_caso): lo que pase aquí no se rechaza
// después por los datos, salvo que el catálogo cambie mientras tanto.
fun erroresDe(estado: EstadoCaptura, hoy: LocalDate): List<String> = buildList {
    if (estado.enfermedad == null) add("Elige la enfermedad.")
    if (estado.municipio == null) add("Elige el municipio.")
    if (estado.fechaReporte > hoy) add("La fecha de reporte no puede estar en el futuro.")
    estado.inicioSintomas?.let {
        if (it > estado.fechaReporte) add("El inicio de síntomas no puede ser posterior a la fecha de reporte.")
    }
    if (estado.edad.isNotEmpty() && estado.edad.toIntOrNull() !in 0..120) add("La edad va de 0 a 120 años.")
}

// Guarda en el teléfono y pide el envío: el caso se manda cuando haya red, aunque se cierre la app.
class CapturaViewModel(
    private val sesion: Sesion,
    private val casos: CasosDao,
    catalogo: CatalogoDao,
    private val catalogos: Catalogos,
    private val programarEnvio: () -> Unit,
    private val ubicador: Ubicador,
    private val hoy: () -> LocalDate = { LocalDate.now() },
    private val ahora: () -> Long = System::currentTimeMillis,
) : ViewModel() {
    var estado by mutableStateOf(EstadoCaptura(fechaReporte = hoy()))
        private set

    init {
        viewModelScope.launch {
            combine(catalogo.enfermedades(), catalogo.municipios(), ::Pair).collect { (enfermedades, municipios) ->
                estado = estado.copy(enfermedades = enfermedades, municipios = municipios)
            }
        }
    }

    fun elegirEnfermedad(id: Long) = cambiar { copy(enfermedad = id) }
    fun elegirMunicipio(id: Long) = cambiar { copy(municipio = id) }
    fun cambiarFechaReporte(dia: LocalDate) = cambiar { copy(fechaReporte = dia) }
    fun cambiarInicioSintomas(dia: LocalDate?) = cambiar { copy(inicioSintomas = dia) }
    fun cambiarEdad(texto: String) = cambiar { copy(edad = texto.filter(Char::isDigit).take(3)) }

    // Tocar el que ya estaba elegido lo quita: los tres son opcionales.
    fun elegirSexo(valor: String) = cambiar { copy(sexo = valor.takeIf { it != sexo }) }
    fun elegirResultado(valor: String?) = cambiar { copy(resultadoPrueba = valor) }
    fun elegirSeveridad(valor: String?) = cambiar { copy(severidad = valor) }

    private fun cambiar(cambio: EstadoCaptura.() -> EstadoCaptura) {
        estado = estado.cambio().copy(errores = emptyList())
    }

    // La pantalla ya pidió el permiso; `precisa` dice si se dio el fino o solo el aproximado.
    fun ubicar(precisa: Boolean) {
        if (estado.ubicando) return
        estado = estado.copy(ubicando = true, errorUbicacion = null, sinPermisoDeUbicacion = false)
        viewModelScope.launch {
            val lectura = try {
                ubicador.leer(precisa)
            } catch (e: CancellationException) {
                throw e
            } catch (e: SecurityException) {
                // Quitaron el permiso desde Ajustes entre que se pidió y se leyó.
                estado = estado.copy(ubicando = false, sinPermisoDeUbicacion = true, errorUbicacion = SIN_PERMISO)
                return@launch
            }
            estado = when (lectura) {
                is Lectura.Lista -> estado.copy(ubicando = false, ubicacion = lectura.ubicacion)
                Lectura.Apagada -> estado.copy(
                    ubicando = false, errorUbicacion = "La ubicación del teléfono está apagada. Actívala y vuelve a intentarlo.",
                )
                Lectura.SinSenal -> estado.copy(
                    ubicando = false, errorUbicacion = "No llegó la señal del GPS. Intenta de nuevo, de preferencia a cielo abierto.",
                )
            }
        }
    }

    fun sinPermisoDeUbicacion() {
        estado = estado.copy(sinPermisoDeUbicacion = true, errorUbicacion = SIN_PERMISO)
    }

    fun quitarUbicacion() = cambiar { copy(ubicacion = null, errorUbicacion = null) }

    fun descargarCatalogos() {
        if (estado.descargando) return
        estado = estado.copy(descargando = true, errorCatalogos = null)
        viewModelScope.launch {
            val error = try {
                catalogos.actualizar()
                null
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                mensajeDeError(e)
            }
            estado = estado.copy(descargando = false, errorCatalogos = error)
        }
    }

    fun guardar() {
        if (estado.guardando) return
        val errores = erroresDe(estado, hoy())
        if (errores.isNotEmpty()) {
            estado = estado.copy(errores = errores)
            return
        }
        val datos = estado
        estado = estado.copy(guardando = true)
        viewModelScope.launch {
            val cuenta = sesion.cuenta()
            if (cuenta == null) {
                estado = estado.copy(guardando = false, errores = listOf("La sesión se cerró: vuelve a iniciar sesión."))
                return@launch
            }
            casos.insertar(
                CasoLocal(
                    localUuid = UUID.randomUUID().toString(),
                    cuenta = cuenta,
                    enfermedad = datos.enfermedad!!,
                    municipio = datos.municipio!!,
                    fechaReporte = datos.fechaReporte.toString(),
                    inicioSintomas = datos.inicioSintomas?.toString(),
                    edad = datos.edad.toIntOrNull(),
                    sexo = datos.sexo,
                    resultadoPrueba = datos.resultadoPrueba,
                    severidad = datos.severidad,
                    latitud = datos.ubicacion?.latitud,
                    longitud = datos.ubicacion?.longitud,
                    capturadoEn = ahora(),
                )
            )
            programarEnvio()
            // Se quedan la enfermedad, el municipio y la fecha: en campo se capturan varios casos
            // seguidos de lo mismo. La ubicación es de cada caso: se vuelve a tomar.
            estado = estado.copy(
                guardando = false, inicioSintomas = null, edad = "", sexo = null, resultadoPrueba = null,
                severidad = null, ubicacion = null, errorUbicacion = null, guardados = estado.guardados + 1,
            )
        }
    }

    private companion object {
        const val SIN_PERMISO = "Sin permiso de ubicación: el caso se guarda sin ella."
    }
}
