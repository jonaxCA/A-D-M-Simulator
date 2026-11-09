package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.Perfil
import retrofit2.http.GET

interface UsuariosApi {
    @GET("api/v1/users/me")
    suspend fun perfil(): Perfil
}
