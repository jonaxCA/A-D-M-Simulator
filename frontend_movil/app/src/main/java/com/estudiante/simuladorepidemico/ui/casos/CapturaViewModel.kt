package com.estudiante.simuladorepidemico.ui.casos

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.local.CasoLocal
import com.estudiante.simuladorepidemico.local.CasosDao
import com.estudiante.simuladorepidemico.local.CatalogoDao
import com.estudiante.simuladorepidemico.local.DatosDeSalud
import com.estudiante.simuladorepidemico.local.cifrados
import com.estudiante.simuladorepidemico.local.salud
import com.estudiante.simuladorepidemico.local.Catalogos
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.local.FotoLocal
import com.estudiante.simuladorepidemico.local.Fotos
import com.estudiante.simuladorepidemico.local.Municipio
import com.estudiante.simuladorepidemico.red.CampoDeFormulario
import com.estudiante.simuladorepidemico.red.Formulario
import com.estudiante.simuladorepidemico.red.json
import com.estudiante.simuladorepidemico.red.mensajeDeError
import com.estudiante.simuladorepidemico.sesion.Cifrador
import com.estudiante.simuladorepidemico.sesion.Sesion
import com.estudiante.simuladorepidemico.ubicacion.Lectura
import com.estudiante.simuladorepidemico.ubicacion.Ubicacion
import com.estudiante.simuladorepidemico.ubicacion.Ubicador
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File
import java.io.InputStream
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
    // Lo que le faltó al último caso guardado (D49): se avisa al guardarlo, sin impedirlo.
    val faltantesDelGuardado: List<String> = emptyList(),
    val descargando: Boolean = false,
    val errorCatalogos: String? = null,
    val ubicacion: Ubicacion? = null,
    val ubicando: Boolean = false,
    val errorUbicacion: String? = null,
    val sinPermisoDeUbicacion: Boolean = false,
    val fotos: List<String> = emptyList(),
    val agregandoFoto: Boolean = false,
    val errorFoto: String? = null,
    // El formulario de cada enfermedad (D48) y lo que se va contestando, como texto por clave.
    val formularios: Map<Long, Formulario> = emptyMap(),
    val respuestas: Map<String, String> = emptyMap(),
    // Coordenadas escritas a mano, cuando el GPS no conviene (bajo techo, o se captura después).
    val manual: Boolean = false,
    val latitudManual: String = "",
    val longitudManual: String = "",
    // Hay otro caso igual en el teléfono: se guarda solo si la persona lo confirma.
    val posibleDuplicado: Boolean = false,
) {
    val formulario: Formulario?
        get() = enfermedad?.let { formularios[it] }

    val sinCatalogos: Boolean
        get() = enfermedades.isEmpty() || municipios.isEmpty()

    val caben: Boolean
        get() = fotos.size < MAXIMO_DE_FOTOS && !agregandoFoto
}

// Por caso. Cada una se reduce a unos cientos de KB, pero con datos móviles cinco ya pesan.
const val MAXIMO_DE_FOTOS = 5

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
    if (estado.manual && coordenadasManuales(estado) == null) {
        add("Escribe la latitud (de -90 a 90) y la longitud (de -180 a 180), o quita la ubicación.")
    }
    estado.formulario?.campos?.forEach { campo -> errorDeCampo(campo, estado.respuestas[campo.clave].orEmpty())?.let(::add) }
}

fun coordenadasManuales(estado: EstadoCaptura): Pair<Double, Double>? {
    val latitud = estado.latitudManual.replace(',', '.').toDoubleOrNull() ?: return null
    val longitud = estado.longitudManual.replace(',', '.').toDoubleOrNull() ?: return null
    return (latitud to longitud).takeIf { latitud in -90.0..90.0 && longitud in -180.0..180.0 }
}

// Las mismas reglas que casos al validar las respuestas (formularios.py): obligatorio, tipo y rango.
fun errorDeCampo(campo: CampoDeFormulario, texto: String): String? {
    if (texto.isBlank()) return if (campo.obligatorio) "Falta «${campo.etiqueta}»." else null
    fun numero(valor: Double?) = valor?.let { if (it % 1.0 == 0.0) it.toLong().toString() else it.toString() }
    val fueraDeRango = "«${campo.etiqueta}» va de ${numero(campo.minimo) ?: "-∞"} a ${numero(campo.maximo) ?: "∞"}."
    return when (campo.tipo) {
        "entero", "decimal" -> {
            val numero = (if (campo.tipo == "entero") texto.toLongOrNull()?.toDouble() else texto.replace(',', '.').toDoubleOrNull())
                ?: return "«${campo.etiqueta}» es un número${if (campo.tipo == "entero") " entero" else ""}."
            fueraDeRango.takeIf { campo.minimo?.let { numero < it } == true || campo.maximo?.let { numero > it } == true }
        }
        "texto" -> "«${campo.etiqueta}» admite hasta ${campo.largoMaximo} caracteres."
            .takeIf { campo.largoMaximo != null && texto.length > campo.largoMaximo }
        "fecha" -> "«${campo.etiqueta}» es una fecha.".takeIf { runCatching { LocalDate.parse(texto) }.isFailure }
        else -> null
    }
}

// Las respuestas con su tipo, como las espera casos. Lo vacío no viaja.
fun respuestasDe(formulario: Formulario, respuestas: Map<String, String>): JsonObject = buildJsonObject {
    formulario.campos.forEach { campo ->
        val texto = respuestas[campo.clave].orEmpty()
        if (texto.isBlank()) return@forEach
        when (campo.tipo) {
            "entero" -> put(campo.clave, texto.toLong())
            "decimal" -> put(campo.clave, texto.replace(',', '.').toDouble())
            "booleano" -> put(campo.clave, texto == "true")
            "opciones" -> put(campo.clave, JsonArray(texto.split(',').map(::JsonPrimitive)))
            else -> put(campo.clave, texto)
        }
    }
}

// Control de calidad: lo que casos marca como incompleto (D49). No impide guardar.
fun faltantesDe(estado: EstadoCaptura): List<String> = listOfNotNull(
    "edad".takeIf { estado.edad.isEmpty() },
    "sexo".takeIf { estado.sexo == null },
    "inicio de síntomas".takeIf { estado.inicioSintomas == null },
    "resultado".takeIf { estado.resultadoPrueba == null },
    "gravedad".takeIf { estado.severidad == null },
    "ubicación".takeIf { estado.ubicacion == null && !estado.manual },
)

// Guarda en el teléfono y pide el envío: el caso se manda cuando haya red, aunque se cierre la app.
class CapturaViewModel(
    private val sesion: Sesion,
    private val casos: CasosDao,
    catalogo: CatalogoDao,
    private val catalogos: Catalogos,
    private val programarEnvio: () -> Unit,
    private val ubicador: Ubicador,
    private val fotos: Fotos,
    private val cifrador: Cifrador,
    private val hoy: () -> LocalDate = { LocalDate.now() },
    private val ahora: () -> Long = System::currentTimeMillis,
) : ViewModel() {
    var estado by mutableStateOf(EstadoCaptura(fechaReporte = hoy()))
        private set

    init {
        // Un solo formulario a la vez: lo que haya en borradores es de uno que no se guardó.
        fotos.limpiarBorradores()
        viewModelScope.launch {
            combine(catalogo.enfermedades(), catalogo.municipios(), catalogo.formularios(), ::Triple)
                .collect { (enfermedades, municipios, formularios) ->
                    estado = estado.copy(
                        enfermedades = enfermedades, municipios = municipios,
                        formularios = formularios.associate { it.enfermedad to json.decodeFromString<Formulario>(it.json) },
                    )
                }
        }
    }

    // Otra enfermedad trae otro formulario: las respuestas no pasan de uno a otro.
    fun elegirEnfermedad(id: Long) = cambiar { copy(enfermedad = id, respuestas = if (id == enfermedad) respuestas else emptyMap()) }
    fun cambiarRespuesta(clave: String, valor: String) = cambiar { copy(respuestas = respuestas + (clave to valor)) }
    fun escribirUbicacion(latitud: String, longitud: String) = cambiar { copy(latitudManual = latitud, longitudManual = longitud) }

    // Escribir las coordenadas reemplaza a las del GPS, y al revés.
    fun alternarManual() = cambiar {
        copy(manual = !manual, ubicacion = null, errorUbicacion = null, latitudManual = "", longitudManual = "")
    }
    fun elegirMunicipio(id: Long) = cambiar { copy(municipio = id) }
    fun cambiarFechaReporte(dia: LocalDate) = cambiar { copy(fechaReporte = dia) }
    fun cambiarInicioSintomas(dia: LocalDate?) = cambiar { copy(inicioSintomas = dia) }
    fun cambiarEdad(texto: String) = cambiar { copy(edad = texto.filter(Char::isDigit).take(3)) }

    // Tocar el que ya estaba elegido lo quita: los tres son opcionales.
    fun elegirSexo(valor: String) = cambiar { copy(sexo = valor.takeIf { it != sexo }) }
    fun elegirResultado(valor: String?) = cambiar { copy(resultadoPrueba = valor) }
    fun elegirSeveridad(valor: String?) = cambiar { copy(severidad = valor) }

    private fun cambiar(cambio: EstadoCaptura.() -> EstadoCaptura) {
        estado = estado.cambio().copy(errores = emptyList(), posibleDuplicado = false)
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

    // Donde la app de cámara deja la foto completa. agregarDeCamara la reduce y la borra.
    fun archivoParaLaCamara(): File = fotos.paraLaCamara()

    fun archivoDeFoto(id: String): File = fotos.vista(id)

    // La foto completa de la cámara no se queda: puede traer la ubicación en su EXIF.
    fun agregarDeCamara(archivo: File) = agregarFoto({ archivo.inputStream() }, alTerminar = { archivo.delete() })

    // `abrir` lee la foto (de la galería, o el archivo de la cámara); se reduce y queda como borrador.
    fun agregarFoto(abrir: () -> InputStream, alTerminar: () -> Unit = {}) {
        if (!estado.caben) {
            alTerminar()
            return
        }
        estado = estado.copy(agregandoFoto = true, errorFoto = null)
        viewModelScope.launch {
            try {
                val id = fotos.importar(abrir)
                estado = estado.copy(agregandoFoto = false, fotos = estado.fotos + id)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado = estado.copy(agregandoFoto = false, errorFoto = "No se pudo leer la foto. Intenta con otra.")
            } finally {
                alTerminar()
            }
        }
    }

    fun errorDeFoto(mensaje: String) {
        estado = estado.copy(errorFoto = mensaje)
    }

    fun quitarFoto(id: String) {
        fotos.borrar(listOf(id))
        estado = estado.copy(fotos = estado.fotos - id)
    }

    // Salir sin guardar no deja fotos en el teléfono.
    override fun onCleared() {
        fotos.borrar(estado.fotos)
    }

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

    // `confirmado`: la persona ya vio el aviso de posible duplicado y lo guarda de todos modos.
    fun guardar(confirmado: Boolean = false) {
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
            val repetido = !confirmado && casos.parecidos(cuenta, datos.enfermedad!!, datos.municipio!!, datos.fechaReporte.toString())
                .map { it.salud(cifrador) }.any { it.edad == datos.edad.toIntOrNull() && it.sexo == datos.sexo }
            if (repetido) {
                estado = estado.copy(guardando = false, posibleDuplicado = true)
                return@launch
            }
            val coordenadas = datos.ubicacion?.let { it.latitud to it.longitud } ?: coordenadasManuales(datos).takeIf { datos.manual }
            val caso = CasoLocal(
                localUuid = UUID.randomUUID().toString(),
                cuenta = cuenta,
                enfermedad = datos.enfermedad!!,
                municipio = datos.municipio!!,
                fechaReporte = datos.fechaReporte.toString(),
                capturadoEn = ahora(),
                formulario = datos.formulario?.id,
                datos = DatosDeSalud(
                    inicioSintomas = datos.inicioSintomas?.toString(),
                    edad = datos.edad.toIntOrNull(),
                    sexo = datos.sexo,
                    resultadoPrueba = datos.resultadoPrueba,
                    severidad = datos.severidad,
                    latitud = coordenadas?.first,
                    longitud = coordenadas?.second,
                    respuestas = datos.formulario?.let { respuestasDe(it, datos.respuestas) }?.takeIf { it.isNotEmpty() },
                ).cifrados(cifrador),
            )
            // tomadaEn sigue el orden en que se agregaron.
            val filas = datos.fotos.mapIndexed { i, id -> FotoLocal(id, caso.localUuid, tomadaEn = caso.capturadoEn + i) }
            try {
                fotos.confirmar(datos.fotos)
                casos.capturar(caso, filas)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado = estado.copy(guardando = false, errores = listOf("No se pudo guardar el caso en el teléfono."))
                return@launch
            }
            programarEnvio()
            // Se quedan la enfermedad, el municipio y la fecha: en campo se capturan varios casos
            // seguidos de lo mismo. La ubicación y las fotos son de cada caso.
            estado = estado.copy(
                guardando = false, inicioSintomas = null, edad = "", sexo = null, resultadoPrueba = null,
                severidad = null, ubicacion = null, errorUbicacion = null, fotos = emptyList(), errorFoto = null,
                respuestas = emptyMap(), latitudManual = "", longitudManual = "", posibleDuplicado = false,
                faltantesDelGuardado = faltantesDe(datos), guardados = estado.guardados + 1,
            )
        }
    }

    private companion object {
        const val SIN_PERMISO = "Sin permiso de ubicación: el caso se guarda sin ella."
    }
}
