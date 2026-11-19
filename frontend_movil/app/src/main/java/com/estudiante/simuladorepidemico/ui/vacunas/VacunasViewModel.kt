package com.estudiante.simuladorepidemico.ui.vacunas

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.local.CatalogoDao
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.local.Municipio
import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.red.LoteVacuna
import com.estudiante.simuladorepidemico.red.PedidoDosis
import com.estudiante.simuladorepidemico.red.PedidoLoteVacuna
import com.estudiante.simuladorepidemico.red.mensajeDeError
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException
import java.time.LocalDate

enum class Paso { ESCANEAR, BUSCANDO, LOTE, REGISTRAR }

data class DatosLote(
    val enfermedad: Long? = null,
    val dosisTotales: String = "",
    val fabricante: String = "",
    val municipio: Long? = null,
    val caducidad: LocalDate? = null,
)

data class EstadoVacunas(
    val paso: Paso = Paso.ESCANEAR,
    val escrito: String = "",
    val codigo: String = "",
    val lote: LoteVacuna? = null,
    val dosis: Int = 1,
    val aplicando: Boolean = false,
    val aviso: String? = null,
    val error: String? = null,
    val registro: DatosLote = DatosLote(),
    val registrando: Boolean = false,
    val enfermedades: List<Enfermedad> = emptyList(),
    val municipios: List<Municipio> = emptyList(),
) {
    // Por aplicación: vacunas acepta de 1 a 1,000, y nunca más de las que quedan.
    val maximoDeDosis: Int
        get() = minOf(lote?.dosisRestantes ?: 0, APLICAR_MAXIMO)
}

const val APLICAR_MAXIMO = 1000

// Como lo valida vacunas: de 1 a 60 caracteres visibles, sin espacios.
private val CODIGO = Regex("^[\\x21-\\x7e]{1,60}$")
private const val SIN_RED = "Sin conexión: consultar lotes y aplicar dosis necesita red."

// Escanear (o escribir) el código, buscar el lote, registrarlo si no existe y aplicar dosis
// (README, sección 8). Todo necesita red: quien garantiza que no se apliquen más dosis de las que
// trae el lote es el servidor.
class VacunasViewModel(private val apis: Apis, catalogo: CatalogoDao) : ViewModel() {
    var estado by mutableStateOf(EstadoVacunas())
        private set

    init {
        viewModelScope.launch {
            combine(catalogo.enfermedades(), catalogo.municipios(), ::Pair).collect { (enfermedades, municipios) ->
                estado = estado.copy(enfermedades = enfermedades, municipios = municipios)
            }
        }
    }

    fun cambiarEscrito(texto: String) {
        estado = estado.copy(escrito = texto.trim().take(60), error = null)
    }

    fun buscarEscrito() = leido(estado.escrito)

    // La cámara lee varias veces por segundo: solo cuenta la primera mientras se está escaneando.
    fun leido(codigo: String) {
        if (estado.paso != Paso.ESCANEAR) return
        val limpio = codigo.trim()
        if (!CODIGO.matches(limpio)) {
            estado = estado.copy(error = "Ese código no parece de un lote: son de 1 a 60 letras, números o signos, sin espacios.")
            return
        }
        estado = estado.copy(paso = Paso.BUSCANDO, codigo = limpio, error = null, aviso = null)
        viewModelScope.launch {
            estado = try {
                val lote = apis.vacunas().buscar(limpio).lotes.firstOrNull { it.codigo == limpio }
                if (lote != null) estado.copy(paso = Paso.LOTE, lote = lote, dosis = 1)
                else estado.copy(paso = Paso.REGISTRAR, registro = DatosLote())
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado.copy(paso = Paso.ESCANEAR, error = if (e is IOException) SIN_RED else mensajeDeError(e))
            }
        }
    }

    fun otroCodigo() {
        estado = EstadoVacunas(enfermedades = estado.enfermedades, municipios = estado.municipios)
    }

    fun cambiarDosis(n: Int) {
        estado = estado.copy(dosis = n.coerceIn(1, maxOf(1, estado.maximoDeDosis)), aviso = null)
    }

    fun aplicar() {
        val lote = estado.lote ?: return
        if (estado.aplicando) return
        if (lote.vencido) {
            estado = estado.copy(error = "Este lote caducó: ya no se le pueden aplicar dosis.")
            return
        }
        val dosis = estado.dosis
        if (dosis > lote.dosisRestantes) {
            estado = estado.copy(error = "Al lote le quedan ${lote.dosisRestantes} dosis.")
            return
        }
        estado = estado.copy(aplicando = true, error = null, aviso = null)
        viewModelScope.launch {
            try {
                val nuevo = apis.vacunas().aplicar(lote.id, PedidoDosis(dosis))
                estado = estado.copy(
                    aplicando = false, lote = nuevo, dosis = 1,
                    aviso = "Se aplicaron $dosis dosis. Quedan ${nuevo.dosisRestantes}.",
                )
            } catch (e: CancellationException) {
                throw e
            } catch (e: HttpException) {
                // 409: no alcanzan o caducó (otro teléfono pudo aplicar mientras tanto).
                estado = estado.copy(aplicando = false, error = mensajeDeError(e))
                refrescar(lote.id)
            } catch (e: IOException) {
                // No se sabe si llegó: no se reintenta solo, porque aplicar dos veces descontaría
                // de más. Se muestra cómo quedó el lote.
                estado = estado.copy(
                    aplicando = false,
                    error = "No se pudo confirmar si se aplicaron. Revisa las dosis del lote antes de volver a intentarlo.",
                )
                refrescar(lote.id)
            }
        }
    }

    private suspend fun refrescar(id: Long) {
        try {
            val lote = apis.vacunas().consultar(id)
            estado = estado.copy(lote = lote, dosis = estado.dosis.coerceIn(1, maxOf(1, minOf(lote.dosisRestantes, APLICAR_MAXIMO))))
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            // Se queda lo que había en pantalla, con el error de arriba.
        }
    }

    fun cambiarRegistro(cambio: DatosLote.() -> DatosLote) {
        estado = estado.copy(registro = estado.registro.cambio(), error = null)
    }

    fun registrar() {
        if (estado.registrando) return
        val datos = estado.registro
        val enfermedad = datos.enfermedad
        val dosis = datos.dosisTotales.toIntOrNull()
        val error = when {
            enfermedad == null -> "Elige la enfermedad del lote."
            dosis == null || dosis !in 1..1_000_000 -> "Las dosis del lote van de 1 a 1,000,000."
            datos.fabricante.length > 120 -> "El fabricante es de hasta 120 caracteres."
            else -> null
        }
        if (error != null || enfermedad == null || dosis == null) {
            estado = estado.copy(error = error)
            return
        }
        val codigo = estado.codigo
        estado = estado.copy(registrando = true, error = null)
        viewModelScope.launch {
            val pedido = PedidoLoteVacuna(
                codigo = codigo, enfermedad = enfermedad, dosisTotales = dosis,
                fabricante = datos.fabricante.trim().ifEmpty { null }, municipio = datos.municipio,
                caducidad = datos.caducidad?.toString(),
            )
            try {
                val lote = apis.vacunas().registrar(pedido)
                estado = estado.copy(
                    registrando = false, paso = Paso.LOTE, lote = lote, dosis = 1, aviso = "Lote registrado.",
                )
            } catch (e: CancellationException) {
                throw e
            } catch (e: HttpException) {
                // 409: alguien lo registró con otros datos mientras tanto. Se muestran los suyos.
                val mensaje = mensajeDeError(e)
                val ya = if (e.code() == 409) buscarDeNuevo(codigo) else null
                estado = if (ya != null) {
                    estado.copy(registrando = false, paso = Paso.LOTE, lote = ya, dosis = 1, error = "$mensaje Estos son sus datos.")
                } else {
                    estado.copy(registrando = false, error = mensaje)
                }
            } catch (e: IOException) {
                estado = estado.copy(registrando = false, error = SIN_RED)
            }
        }
    }

    private suspend fun buscarDeNuevo(codigo: String): LoteVacuna? = try {
        apis.vacunas().buscar(codigo).lotes.firstOrNull { it.codigo == codigo }
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        null
    }
}
