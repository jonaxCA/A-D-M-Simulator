package com.estudiante.simuladorepidemico.local

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

// Lo que acepta casos: enfermedades vigentes y los municipios de Nuevo León.
@Entity(tableName = "enfermedades")
data class Enfermedad(@PrimaryKey val id: Long, val nombre: String)

@Entity(tableName = "municipios")
data class Municipio(@PrimaryKey val id: Long, val nombre: String)

// La versión vigente del formulario de una enfermedad (D48), como la manda casos.
@Entity(tableName = "formularios")
data class FormularioLocal(@PrimaryKey val enfermedad: Long, val id: Long, val json: String)

@Dao
abstract class CatalogoDao {
    @Query("SELECT * FROM enfermedades ORDER BY nombre COLLATE LOCALIZED")
    abstract fun enfermedades(): Flow<List<Enfermedad>>

    @Query("SELECT * FROM municipios ORDER BY nombre COLLATE LOCALIZED")
    abstract fun municipios(): Flow<List<Municipio>>

    @Query("SELECT * FROM formularios")
    abstract fun formularios(): Flow<List<FormularioLocal>>

    @Query("DELETE FROM formularios")
    abstract suspend fun borrarFormularios()

    @Insert
    abstract suspend fun insertarFormularios(lista: List<FormularioLocal>)

    @Transaction
    open suspend fun reemplazarFormularios(lista: List<FormularioLocal>) {
        borrarFormularios()
        insertarFormularios(lista)
    }

    @Query("DELETE FROM enfermedades")
    abstract suspend fun borrarEnfermedades()

    @Query("DELETE FROM municipios")
    abstract suspend fun borrarMunicipios()

    @Insert
    abstract suspend fun insertarEnfermedades(lista: List<Enfermedad>)

    @Insert
    abstract suspend fun insertarMunicipios(lista: List<Municipio>)

    // Todo o nada: una enfermedad que se desactivó deja de ofrecerse.
    @Transaction
    open suspend fun reemplazar(enfermedades: List<Enfermedad>, municipios: List<Municipio>) {
        borrarEnfermedades()
        borrarMunicipios()
        insertarEnfermedades(enfermedades)
        insertarMunicipios(municipios)
    }
}
