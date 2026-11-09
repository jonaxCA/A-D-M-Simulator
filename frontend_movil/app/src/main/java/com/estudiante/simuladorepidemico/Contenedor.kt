package com.estudiante.simuladorepidemico

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import com.estudiante.simuladorepidemico.avisos.Avisos
import com.estudiante.simuladorepidemico.local.CasosDao
import com.estudiante.simuladorepidemico.local.CatalogoDao
import com.estudiante.simuladorepidemico.local.Catalogos
import com.estudiante.simuladorepidemico.local.Fotos
import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.red.Directorio
import com.estudiante.simuladorepidemico.red.Renovador
import com.estudiante.simuladorepidemico.red.api.EstadoServiciosApi
import com.estudiante.simuladorepidemico.red.api.SesionesApi
import com.estudiante.simuladorepidemico.red.clienteBase
import com.estudiante.simuladorepidemico.red.clienteConToken
import com.estudiante.simuladorepidemico.red.retrofit
import com.estudiante.simuladorepidemico.sesion.AlmacenSesion
import com.estudiante.simuladorepidemico.sesion.Cifrador
import com.estudiante.simuladorepidemico.sesion.DescripcionTelefono
import com.estudiante.simuladorepidemico.sesion.Sesion
import com.estudiante.simuladorepidemico.sesion.Telefono
import com.estudiante.simuladorepidemico.trabajos.Sincronizador
import com.estudiante.simuladorepidemico.ubicacion.Ubicador

// Las dependencias de la app, armadas a mano. `programarEnvio` pide que se manden los casos
// pendientes en cuanto haya red, y `programarAvisos`, la consulta periódica de avisos (WorkManager
// en la app; en las pruebas, nada o un contador).
class Contenedor(
    datos: DataStore<Preferences>,
    cifrador: Cifrador,
    directorioUrl: String,
    telefono: DescripcionTelefono,
    val casos: CasosDao,
    val catalogo: CatalogoDao,
    val programarEnvio: () -> Unit,
    val ubicador: Ubicador,
    val fotos: Fotos,
    val programarAvisos: () -> Unit,
) {
    val almacen = AlmacenSesion(datos, cifrador)
    private val sinToken = clienteBase()
    private val directorio = Directorio(
        retrofit(directorioUrl.trimEnd('/') + "/", sinToken).create(EstadoServiciosApi::class.java)
    )
    private val renovador = Renovador(almacen) {
        retrofit(directorio.url("sesiones"), sinToken).create(SesionesApi::class.java)
    }
    val apis = Apis(directorio, clienteConToken(sinToken, almacen, renovador), sinToken)
    val sesion = Sesion(apis, almacen, Telefono(datos, apis, telefono))
    val catalogos = Catalogos(apis, catalogo)
    val sincronizador = Sincronizador(sesion, apis, casos, fotos)
    val avisos = Avisos(apis, datos, sesion)
}
