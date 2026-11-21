package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.ListaServicios
import retrofit2.Call
import retrofit2.http.GET

interface EstadoServiciosApi {
    @GET("api/v1/services")
    fun servicios(): Call<ListaServicios>
}
