package com.estudiante.simuladorepidemico.red

import com.estudiante.simuladorepidemico.red.api.EstadoServiciosApi
import java.io.IOException

// No hay pasarela (D13): estado-servicios dice dónde está cada servicio.
class Directorio(private val api: EstadoServiciosApi) {
    @Volatile
    private var urls: Map<String, String> = emptyMap()

    // Bloquea la primera vez: llámala fuera del hilo principal.
    fun url(servicio: String): String {
        urls[servicio]?.let { return it }
        synchronized(this) {
            if (servicio !in urls) {
                val respuesta = api.servicios().execute()
                val lista = respuesta.body()
                if (!respuesta.isSuccessful || lista == null) {
                    throw IOException("El directorio respondió ${respuesta.code()}.")
                }
                urls = lista.servicios.associate { it.nombre to it.url.trimEnd('/') + "/" }
            }
        }
        return urls[servicio] ?: throw IOException("El directorio no tiene el servicio $servicio.")
    }
}
