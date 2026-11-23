package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.CasoRemoto
import com.estudiante.simuladorepidemico.red.HistorialDeCaso
import com.estudiante.simuladorepidemico.red.ListaCasosRemotos
import com.estudiante.simuladorepidemico.red.ListaFormularios
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.PATCH
import retrofit2.http.Path
import retrofit2.http.Query

// Los casos ya en el servidor (D47, D49) y los formularios por enfermedad (D48). La captura no pasa
// por aquí: va en lotes a sincronizacion.
interface CasosApi {
    @GET("api/v1/cases/incomplete")
    suspend fun incompletos(@Query("per_page") tamano: Int = 100): ListaCasosRemotos

    @GET("api/v1/cases/{id}")
    suspend fun caso(@Path("id") id: Long): CasoRemoto

    // If-Match lleva la versión que se leyó: si alguien más cambió el caso, 412 y nada se toca.
    @PATCH("api/v1/cases/{id}")
    suspend fun corregir(@Path("id") id: Long, @Header("If-Match") version: String, @Body cambios: JsonObject): CasoRemoto

    @GET("api/v1/cases/{id}/history")
    suspend fun historial(@Path("id") id: Long): HistorialDeCaso

    @GET("api/v1/forms/current")
    suspend fun formularios(): ListaFormularios
}
