"""
Corpus de formularios para caracterizar las funciones valida_* de queries.py.

Cada caso es (descripcion, validador, formulario). test_caracterizacion_formularios
fija, por caso, los datos convertidos y la lista exacta de errores. Entre todos
tienen que pasar por cada `errores.append` de backend_web/conversion.py
(test_conversion lo comprueba).

Las entradas son las que puede mandar un POST armado a mano: vacios, espacios,
comas de miles, notacion cientifica, digitos no latinos, NaN. No hay fechas en
formatos que solo acepta Python 3.11+, porque el codigo debe correr en 3.9.
"""

REGIONES = [
    {"id": 1, "grupos": {"0-19": 1500, "20-59": 2800, "60+": 700}, "sin_edad": 12},
    {"id": 2, "grupos": {}, "sin_edad": 0},
    {"id": 3, "grupos": {"0-19": 10, "20-59": 20, "60+": 5}, "sin_edad": 0},
]
ENFERMEDADES = [
    {"id": 1, "name": "Simulable", "simulable": True, "faltan": 0, "sin_fuente": 0},
    {"id": 2, "name": "Incompleta", "simulable": False, "faltan": 2, "sin_fuente": 1},
]
PARAMETROS_ENFERMEDAD = {
    "r0": {"valor": 2.1, "fuente": "Fuente de prueba", "supuesto": False},
    "incubacion_dias": {"valor": 4.0, "fuente": None, "supuesto": True},
    "infeccioso_dias": {"valor": 6.0, "fuente": None, "supuesto": True},
    "tasa_hospitalizacion": {"valor": 0.04, "fuente": None, "supuesto": True},
    "letalidad": {"valor": 0.006, "fuente": None, "supuesto": True},
    "dias_hospitalizacion": {"valor": 7.5, "fuente": None, "supuesto": True},
}
TIPOS = [
    {"id": 7, "code": "PRUEBA", "name": "Tipo de prueba", "param_schema": {
        "required": ["dias"],
        "properties": {
            "dias": {"type": "integer", "minimum": 1, "maximum": 30},
            "fraccion": {"type": "number", "minimum": 0, "maximum": 1},
            "desde": {"type": "integer", "minimum": 5},
            "libre": {"type": "number"},
            "modo": {"enum": ["a", "b"]},
            "grupos": {"type": "array"},
            "nota": {"type": "string"},
        }}},
    {"id": 8, "code": "SIN_PARAMS", "name": "Sin parametros", "param_schema": None},
]
VERSION = {"horizon_days": 120}
EXISTENTES = [{"code": "PRUEBA", "start_day": 50, "end_day": 60}]

# None = el campo no viene en el formulario.
ENTEROS = [None, "", "   ", "0", "1", "-1", " 42 ", "abc", "1,000", "1,000,000",
           "1.5", "1e3", "+7", "1_000", "٣", "２", "2147483647", "2147483648",
           ",", "--1", "120", "121"]
FECHAS = [None, "", " ", "2025-01-15", " 2025-01-15 ", "2025-02-30", "2025-13-01",
          "15/01/2025", "abc", "2999-01-01", "0001-01-01"]
DECIMALES = [None, "", "0", "-90", "90", "90.0001", "-180.5", "abc", "nan", "inf",
             "1e1", "1,5", " 25.6 "]
NUMEROS = ["0", "1", "5", "30", "31", "-0", "0.5", "1.5", "-0.1", "abc", "1,000",
           "nan", "inf", "-inf", "1e-3", "7.0"]

CASO_BASE = {"disease_id": "1", "region_id": "1", "report_date": "2025-01-15",
             "onset_date": "2025-01-10", "age": "30", "latitude": "25.6",
             "longitude": "-100.3", "sex": "F", "test_result": "", "severity": ""}
# Sin nombre a proposito: con un error en el formulario valida_escenario no
# consulta la base, y la prueba no la necesita.
ESCENARIO_BASE = {"name": "", "region_id": "1", "disease_id": "1",
                  "horizon_days": "90", "population_size": "50000",
                  "initial_infected": "10"}
VERSION_BASE = {"horizon_days": "90", "population_size": "50000",
                "initial_infected": "10", "notes": "Cambio de prueba"}
INTERVENCION_BASE = {"code": "PRUEBA", "start_day": "10", "end_day": "20",
                     "coverage": "0.5", "compliance": "0.8", "p_PRUEBA_dias": "5"}


def _con(base, campo, valor):
    form = dict(base)
    if valor is None:
        form.pop(campo, None)
    else:
        form[campo] = valor
    return form


def _variantes(prefijo, validador, base, campos, valores):
    return {f"{prefijo}.{campo}[{valor!r}]": (f"{campo} = {valor!r}", validador,
                                              _con(base, campo, valor))
            for campo in campos for valor in valores}


CASOS = {}
CASOS.update(_variantes("caso", "valida_caso", CASO_BASE,
                        ("disease_id", "region_id", "age"), ENTEROS))
CASOS.update(_variantes("caso", "valida_caso", CASO_BASE,
                        ("report_date", "onset_date"), FECHAS))
CASOS.update(_variantes("caso", "valida_caso", CASO_BASE,
                        ("latitude", "longitude"), DECIMALES))
CASOS.update(_variantes("escenario", "valida_escenario", ESCENARIO_BASE,
                        ("region_id", "disease_id", "horizon_days", "population_size",
                         "initial_infected"), ENTEROS))
CASOS.update(_variantes("version", "valida_version", VERSION_BASE,
                        ("horizon_days", "population_size", "initial_infected"), ENTEROS))
CASOS.update(_variantes("intervencion", "valida_intervencion", INTERVENCION_BASE,
                        ("start_day", "end_day"), ENTEROS))
CASOS.update(_variantes("intervencion", "valida_intervencion", INTERVENCION_BASE,
                        ("p_PRUEBA_dias", "p_PRUEBA_fraccion", "p_PRUEBA_desde",
                         "p_PRUEBA_libre"), NUMEROS))

CASOS.update({
    "caso.vacio": ("Formulario vacio.", "valida_caso", {}),
    "caso.base": ("El caso base, valido.", "valida_caso", CASO_BASE),
    "caso.sin_ubicacion": ("Sin latitud ni longitud.", "valida_caso",
                           _con(_con(CASO_BASE, "latitude", ""), "longitude", "")),
    "caso.inicio_despues_del_reporte": (
        "Sintomas despues del reporte.", "valida_caso",
        _con(CASO_BASE, "onset_date", "2025-02-01")),
    "caso.catalogos_invalidos": (
        "Sexo, resultado y severidad fuera de catalogo.", "valida_caso",
        {**CASO_BASE, "sex": "X", "test_result": "talvez", "severity": "mucha"}),
    "escenario.vacio": ("Formulario vacio.", "valida_escenario", {}),
    "escenario.nombre_largo": ("Nombre de 161 caracteres.", "valida_escenario",
                               _con(ESCENARIO_BASE, "name", "x" * 161)),
    "escenario.region_inexistente": ("Region fuera del catalogo.", "valida_escenario",
                                     _con(ESCENARIO_BASE, "region_id", "99")),
    "escenario.enfermedad_no_simulable": (
        "Enfermedad incompleta.", "valida_escenario",
        _con(ESCENARIO_BASE, "disease_id", "2")),
    "escenario.estratificado_sin_politica": (
        "Estratificado con gente sin edad y sin politica.", "valida_escenario",
        {**ESCENARIO_BASE, "estratificar": "on"}),
    "escenario.estratificado_con_politica": (
        "Estratificado con politica.", "valida_escenario",
        {**ESCENARIO_BASE, "estratificar": "on", "age_unknown_policy": "excluir"}),
    "escenario.estratificado_sin_grupos": (
        "Region sin grupos de edad.", "valida_escenario",
        {**ESCENARIO_BASE, "estratificar": "on", "region_id": "2"}),
    "escenario.iniciales_sobre_poblacion": (
        "Mas infectados que poblacion.", "valida_escenario",
        {**ESCENARIO_BASE, "estratificar": "on", "region_id": "3",
         "initial_infected": "36"}),
    "version.vacio": ("Formulario vacio.", "valida_version", {}),
    "version.base": ("La version base, que llega al motor.", "valida_version",
                     VERSION_BASE),
    "version.sin_notas": ("Sin comentario.", "valida_version",
                          _con(VERSION_BASE, "notes", "")),
    "intervencion.vacio": ("Formulario vacio.", "valida_intervencion", {}),
    "intervencion.base": ("La intervencion base.", "valida_intervencion",
                          INTERVENCION_BASE),
    "intervencion.fin_antes_del_inicio": (
        "Fin antes del inicio.", "valida_intervencion",
        _con(INTERVENCION_BASE, "end_day", "5")),
    "intervencion.traslape": ("Se encima con la existente.", "valida_intervencion",
                              {**INTERVENCION_BASE, "start_day": "55", "end_day": "70"}),
    "intervencion.tipo_desconocido": ("Tipo fuera de catalogo.", "valida_intervencion",
                                      _con(INTERVENCION_BASE, "code", "OTRO")),
    "intervencion.sin_params": ("Tipo sin param_schema.", "valida_intervencion",
                                {"code": "SIN_PARAMS", "start_day": "0"}),
    "intervencion.enum_y_arreglo": (
        "Enum invalido y arreglo con huecos.", "valida_intervencion",
        {**INTERVENCION_BASE, "p_PRUEBA_modo": "c", "p_PRUEBA_grupos": "60+, ,0-19,",
         "p_PRUEBA_nota": " texto "}),
    "intervencion.factores": (
        "Cobertura y cumplimiento fuera de rango.", "valida_intervencion",
        {**INTERVENCION_BASE, "coverage": "abc", "compliance": "1.5"}),
})
