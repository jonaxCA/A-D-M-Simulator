package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.PedidoRenovar
import com.estudiante.simuladorepidemico.red.Tokens
import retrofit2.Call
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST

interface SesionesApi {
    // Sin suspend: el Renovador la ejecuta en el hilo de OkHttp, sin esperar al despachador.
    @POST("api/v1/sessions/refresh")
    fun renovar(@Body pedido: PedidoRenovar): Call<Tokens>

    @POST("api/v1/sessions/logout")
    suspend fun cerrar(): Response<Unit>
}
