package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.ListaZonas
import retrofit2.http.GET
import retrofit2.http.Query

// Casos agregados por municipio, enfermedad y periodo, con el alcance que el servidor dé a la cuenta.
interface ZonasApi {
    @GET("api/v1/zones")
    suspend fun zonas(
        @Query("disease_id") enfermedad: Long?,
        @Query("days") dias: Int,
        @Query("size") tamano: Int = 51,
    ): ListaZonas
}
