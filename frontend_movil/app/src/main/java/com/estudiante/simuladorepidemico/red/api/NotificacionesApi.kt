package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.Aviso
import com.estudiante.simuladorepidemico.red.ListaAvisos
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface NotificacionesApi {
    // Los de la cuenta del token, del más reciente al más viejo. noLeidas = null: todos.
    @GET("api/v1/notifications")
    suspend fun listar(@Query("unread") noLeidas: Boolean?, @Query("limit") limite: Int): ListaAvisos

    // Si ya estaba leído no cambia nada; el de otra persona es 404.
    @POST("api/v1/notifications/{id}/read")
    suspend fun marcarLeido(@Path("id") id: Long): Aviso
}
