package com.estudiante.simuladorepidemico.ui.casos

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.red.CambioDeCaso
import com.estudiante.simuladorepidemico.red.CasoRemoto
import com.estudiante.simuladorepidemico.red.mensajeDeError
import com.estudiante.simuladorepidemico.red.problema
import com.estudiante.simuladorepidemico.sesion.Sesion
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import retrofit2.HttpException
import java.time.LocalDate

data class Correccion(
    val edad: String = "",
    val sexo: String? = null,
    val inicioSintomas: LocalDate? = null,
    val resultadoPrueba: String? = null,
    val severidad: String? = null,
    val motivo: String = "",
)

data class EstadoSeguimiento(
    val cargando: Boolean = true,
    val caso: CasoRemoto? = null,
    val historial: List<CambioDeCaso> = emptyList(),
    val error: String? = null,
    val puedeCorregir: Boolean = false,
    val correccion: Correccion? = null,
    val guardando: Boolean = false,
    // Otra persona cambió el caso desde que se leyó (412): ya se muestra como quedó.
    val conflicto: String? = null,
)

// D47: el CAPTURISTA corrige sus casos mientras siguen pendientes; validar o descartar es del
// EPIDEMIOLOGO. Cada corrección manda en If-Match la versión que se leyó, así que nunca pisa en
// silencio lo que cambió otra persona.
class SeguimientoViewModel(private val apis: Apis, private val sesion: Sesion, private val caseId: Long) : ViewModel() {
    var estado by mutableStateOf(EstadoSeguimiento())
        private set

    init {
        cargar()
    }

    fun cargar(conflicto: String? = null) {
        estado = estado.copy(cargando = true, error = null)
        viewModelScope.launch {
            try {
                val casos = apis.casos()
                val caso = casos.caso(caseId)
                val historial = casos.historial(caseId).cambios.sortedByDescending { it.version }
                val puede = caso.status == "pendiente" && caso.capturadoPor == sesion.cuenta()
                estado = EstadoSeguimiento(cargando = false, caso = caso, historial = historial, puedeCorregir = puede, conflicto = conflicto)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado = estado.copy(cargando = false, error = mensajeDeError(e))
            }
        }
    }

    fun corregir() {
        val caso = estado.caso ?: return
        estado = estado.copy(
            conflicto = null,
            correccion = Correccion(
                edad = caso.age?.toString().orEmpty(), sexo = caso.sex,
                inicioSintomas = caso.inicioSintomas?.let(LocalDate::parse),
                resultadoPrueba = caso.resultadoPrueba, severidad = caso.severity,
            ),
        )
    }

    fun cancelar() {
        estado = estado.copy(correccion = null, error = null)
    }

    fun cambiar(cambio: Correccion.() -> Correccion) {
        estado.correccion?.let { estado = estado.copy(correccion = it.cambio(), error = null) }
    }

    fun guardar() {
        val caso = estado.caso ?: return
        val nueva = estado.correccion ?: return
        if (estado.guardando) return
        val edad = nueva.edad.toIntOrNull()
        if (nueva.edad.isNotEmpty() && edad !in 0..120) {
            estado = estado.copy(error = "La edad va de 0 a 120 años.")
            return
        }
        if (nueva.inicioSintomas != null && nueva.inicioSintomas > LocalDate.parse(caso.fechaReporte)) {
            estado = estado.copy(error = "El inicio de síntomas no puede ser posterior a la fecha de reporte.")
            return
        }
        // Solo lo que cambió: si nada cambió, no hay nada que mandar.
        val cambios = buildJsonObject {
            if (edad != caso.age) put("age", edad)
            if (nueva.sexo != caso.sex) put("sex", nueva.sexo)
            if (nueva.inicioSintomas?.toString() != caso.inicioSintomas) put("onset_date", nueva.inicioSintomas?.toString())
            if (nueva.resultadoPrueba != caso.resultadoPrueba) put("test_result", nueva.resultadoPrueba)
            if (nueva.severidad != caso.severity) put("severity", nueva.severidad)
        }
        if (cambios.isEmpty()) {
            cancelar()
            return
        }
        val pedido = buildJsonObject {
            cambios.forEach { (campo, valor) -> put(campo, valor) }
            nueva.motivo.trim().takeIf { it.isNotEmpty() }?.let { put("reason", it) }
        }
        estado = estado.copy(guardando = true, error = null)
        viewModelScope.launch {
            try {
                apis.casos().corregir(caseId, "\"${caso.version}\"", pedido)
                cargar()
            } catch (e: CancellationException) {
                throw e
            } catch (e: HttpException) {
                if (e.code() == 412) cargar(conflicto = problema(e).detail)
                else estado = estado.copy(guardando = false, error = mensajeDeError(e))
            } catch (e: Exception) {
                estado = estado.copy(guardando = false, error = mensajeDeError(e))
            }
        }
    }
}
