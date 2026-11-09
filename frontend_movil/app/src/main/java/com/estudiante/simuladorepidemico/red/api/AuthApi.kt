package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.Captcha
import com.estudiante.simuladorepidemico.red.Login
import com.estudiante.simuladorepidemico.red.PedidoLogin
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface AuthApi {
    @GET("api/v1/auth/captcha")
    suspend fun captcha(): Captcha

    @POST("api/v1/auth/login")
    suspend fun iniciar(@Body pedido: PedidoLogin): Login
}
