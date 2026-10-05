"""
Corpus de escenarios para caracterizar resolver() (motor/parametros.py).

Cada caso es (descripcion, escenario). Los validos fijan la salida resuelta y
la simulacion; los invalidos fijan la lista exacta de errores, en orden. Entre
todos tienen que pasar por cada `errores.append` y `avisos.append` de
parametros.py: test_caracterizacion_motor lo comprueba con un trazador, asi
que un caso que falte se nota solo.

Los numeros son ilustrativos: no son parametros de ninguna enfermedad real.
"""
import copy

ENFERMEDAD = {
    "r0": {"valor": 2.1, "fuente": "Fuente de prueba A", "supuesto": False},
    "incubacion_dias": {"valor": 4.0, "fuente": None, "supuesto": True},
    "infeccioso_dias": 6.0,                                   # sin fuente: aviso
    "dias_hospitalizacion": {"dist": "gamma", "media": 7.5},  # formato de 010
    "tasa_hospitalizacion": {"valor": 0.04, "fuente": "Fuente de prueba B",
                             "supuesto": False},
    "letalidad": {"valor": 0.006, "fuente": "Fuente de prueba C", "supuesto": False},
}
POR_EDAD = {"0-19": 15000, "20-59": 28000, "60+": 7000}


def _escenario(**cambios):
    e = {"poblacion": 50000, "infectados_iniciales": 10, "dias": 60,
         "enfermedad": copy.deepcopy(ENFERMEDAD), "intervenciones": []}
    e.update(copy.deepcopy(cambios))
    return e


def _enfermedad(quita=(), **cambios):
    enf = copy.deepcopy(ENFERMEDAD)
    for clave in quita:
        enf.pop(clave)
    enf.update(copy.deepcopy(cambios))
    return enf


def _iv(tipo, inicio=5, fin=40, **resto):
    return {"tipo": tipo, "dia_inicio": inicio, "dia_fin": fin, **resto}


VALIDOS = {
    "total_minimo": (
        "Poblacion total, sin intervenciones; formatos numero, valor/fuente y media.",
        _escenario()),
    "por_edad": (
        "Tres grupos de edad, desordenados a proposito: resolver los ordena.",
        _escenario(poblacion={"60+": 7000, "0-19": 15000, "20-59": 28000})),
    "letalidad_por_edad_gana_si_hay_grupos": (
        "Con grupos, la tabla por edad (alias) gana sobre la tasa global.",
        _escenario(poblacion=POR_EDAD, enfermedad=_enfermedad(
            letalidad_por_edad={"valor": {"0-19": 0.0001, "20-59": 0.002, "60+": 0.05},
                                "fuente": "Fuente de prueba D", "supuesto": False},
            tasa_hospitalizacion={"0-19": 0.01, "20-59": 0.03, "60+": 0.12}))),
    "tasa_global_gana_sin_grupos": (
        "Sin grupos, la tasa global gana sobre la tabla por edad.",
        _escenario(enfermedad=_enfermedad(
            letalidad_por_edad={"0-19": 0.0001, "20-59": 0.002, "60+": 0.05}))),
    "edad_desconocida_excluir": (
        "Gente sin edad declarada que se deja fuera (aviso).",
        _escenario(poblacion=POR_EDAD, poblacion_edad_desconocida=313,
                   politica_edad_desconocida="excluir")),
    "edad_desconocida_prorratear": (
        "Gente sin edad declarada repartida por tamanio de grupo (aviso).",
        _escenario(poblacion=POR_EDAD, poblacion_edad_desconocida=313,
                   politica_edad_desconocida="prorratear")),
    "capas_definidas_en_escenario": (
        "Capas de contacto propias en lugar del supuesto.",
        _escenario(capas_contacto={"hogar": 0.4, "escuela": 0.1, "trabajo": 0.2,
                                   "comunidad": 0.3},
                   intervenciones=[_iv("CIERRE_ESCUELAS")])),
    "intervenciones_de_capa": (
        "Las cuatro de capa, con y sin parametros, cobertura y cumplimiento.",
        _escenario(intervenciones=[
            _iv("CIERRE_ESCUELAS", fin=None),
            _iv("REDUCCION_AFORO", params={"reduccion": 0.5}, cobertura=0.8),
            _iv("CUBREBOCAS", params={"eficacia": 0.3}, cumplimiento=0.6),
            _iv("CIERRE_TRABAJO", params={"sectores": ["industria"]}),
        ])),
    "testeo_y_aislamiento": (
        "Testeo con deteccion, retraso y aislamiento por omision.",
        _escenario(intervenciones=[
            _iv("TESTEO_AISLAMIENTO", params={"deteccion": 0.5, "retraso_dias": 2}),
            _iv("TESTEO_AISLAMIENTO", params={"deteccion": 0.3, "retraso_dias": 1,
                                              "dias_aislamiento": 7}),
        ])),
    "vacunacion_por_edad": (
        "Vacunacion por edad descendente desde un inicio de grupo, y otra con "
        "prioridad no soportada y edad minima que no es inicio de grupo.",
        _escenario(poblacion=POR_EDAD, intervenciones=[
            _iv("VACUNACION", params={"eficacia": 0.8, "dosis_diarias": 500,
                                      "prioridad": "edad_desc", "edad_minima": 20}),
            _iv("VACUNACION", params={"eficacia": 0.6, "dosis_diarias": 200,
                                      "prioridad": "esenciales", "edad_minima": 30}),
        ])),
    "vacunacion_sin_grupos": (
        "Vacunacion aleatoria sobre poblacion total.",
        _escenario(intervenciones=[
            _iv("VACUNACION", params={"eficacia": 0.7, "dosis_diarias": 300})])),
    "intervencion_despues_del_horizonte": (
        "Empieza despues del ultimo dia: aviso, no error.",
        _escenario(intervenciones=[_iv("CUBREBOCAS", inicio=90, fin=None,
                                       params={"eficacia": 0.2})])),
    "vacuna_prioridad_no_textual": (
        "La prioridad llega como objeto: aviso y se aplica como aleatoria, igual que "
        "una prioridad desconocida (LIMP-16).",
        _escenario(intervenciones=[_iv("VACUNACION", params={
            "eficacia": 0.7, "dosis_diarias": 300, "prioridad": {"por": "edad"}})])),
}


INVALIDOS = {
    "no_es_objeto": ("El escenario no es un diccionario.", ["no soy un escenario"]),
    "sin_poblacion": ("Falta poblacion.", _escenario(poblacion=None)),
    "grupo_no_entero": ("Un grupo con poblacion no entera.",
                        _escenario(poblacion={"0-19": 1500.5, "20+": 9000})),
    "grupo_mal_nombrado": ("Un grupo sin formato de edad.",
                           _escenario(poblacion={"ninos": 5000, "20+": 9000})),
    "edad_desconocida_no_entera": ("Gente sin edad que no es entero.",
                                   _escenario(poblacion=POR_EDAD,
                                              poblacion_edad_desconocida=-3)),
    "edad_desconocida_sin_grupos": ("Gente sin edad con poblacion total.",
                                    _escenario(poblacion_edad_desconocida=100,
                                               politica_edad_desconocida="excluir")),
    "edad_desconocida_sin_politica": ("Gente sin edad sin politica declarada.",
                                      _escenario(poblacion=POR_EDAD,
                                                 poblacion_edad_desconocida=100)),
    "prorratear_sin_poblacion": ("Prorratear con todos los grupos en cero.",
                                 _escenario(poblacion={"0-19": 0, "20+": 0},
                                            poblacion_edad_desconocida=100,
                                            politica_edad_desconocida="prorratear")),
    "poblacion_fuera_de_rango": ("Poblacion total por debajo del minimo.",
                                 _escenario(poblacion=10, infectados_iniciales=1)),
    "dias_invalidos": ("Horizonte fuera de rango.", _escenario(dias=0)),
    "infectados_invalidos": ("Infectados iniciales en cero.",
                             _escenario(infectados_iniciales=0)),
    "infectados_mas_que_poblacion": ("Mas infectados que poblacion.",
                                     _escenario(infectados_iniciales=60000)),
    "sin_enfermedad": ("Enfermedad que no es diccionario.", _escenario(enfermedad="COVID")),
    "parametros_faltantes": ("Faltan escalares y tasas.",
                             _escenario(enfermedad=_enfermedad(
                                 quita=("r0", "dias_hospitalizacion",
                                        "tasa_hospitalizacion")))),
    "transmisibilidad_sin_r0": ("Probabilidad por contacto en lugar de R0.",
                                _escenario(enfermedad=_enfermedad(
                                    quita=("r0",), transmisibilidad_base=0.05))),
    "escalar_no_positivo": ("Un escalar en cero.",
                            _escenario(enfermedad=_enfermedad(infeccioso_dias=0))),
    "tasa_fuera_de_rango": ("Tasa global mayor que 1.",
                            _escenario(enfermedad=_enfermedad(letalidad=1.5))),
    "tabla_sin_grupos": ("Tabla por edad con poblacion total.",
                         _escenario(enfermedad=_enfermedad(
                             letalidad={"0-19": 0.001, "20+": 0.01}))),
    "tabla_incompleta": ("Tabla por edad a la que le falta un grupo.",
                         _escenario(poblacion=POR_EDAD, enfermedad=_enfermedad(
                             letalidad={"0-19": 0.001, "20-59": 0.01}))),
    "tabla_fuera_de_rango": ("Tabla por edad con un valor mayor que 1.",
                             _escenario(poblacion=POR_EDAD, enfermedad=_enfermedad(
                                 letalidad={"0-19": 0.001, "20-59": 0.01, "60+": 2}))),
    "tasa_de_otro_tipo": ("Tasa que no es numero ni diccionario.",
                          _escenario(enfermedad=_enfermedad(letalidad="alta"))),
    "capas_invalidas": ("Capas que no suman 1.",
                        _escenario(capas_contacto={"hogar": 0.5, "trabajo": 0.2})),
    "intervencion_no_objeto": ("Intervencion que no es diccionario.",
                               _escenario(intervenciones=["CIERRE_ESCUELAS"])),
    "intervencion_tipo_desconocido": ("Tipo que el motor no soporta.",
                                      _escenario(intervenciones=[_iv("TOQUE_DE_QUEDA")])),
    "intervencion_inicio_invalido": ("dia_inicio negativo.",
                                     _escenario(intervenciones=[_iv("CUBREBOCAS", inicio=-1)])),
    "intervencion_fin_antes_de_inicio": ("dia_fin antes que dia_inicio.",
                                         _escenario(intervenciones=[
                                             _iv("CUBREBOCAS", inicio=20, fin=10)])),
    "intervencion_factores_invalidos": ("Cobertura y cumplimiento fuera de rango.",
                                        _escenario(intervenciones=[
                                            _iv("CIERRE_ESCUELAS", cobertura=1.5,
                                                cumplimiento=-0.1)])),
    "capa_sin_fuerza": ("Intervencion de capa sin su parametro obligatorio.",
                        _escenario(intervenciones=[_iv("REDUCCION_AFORO")])),
    "capa_inexistente": ("La capa de la intervencion no esta en capas_contacto.",
                         _escenario(capas_contacto={"hogar": 0.5, "comunidad": 0.5},
                                    intervenciones=[_iv("CIERRE_ESCUELAS")])),
    "testeo_sin_deteccion": ("Testeo sin deteccion.",
                             _escenario(intervenciones=[
                                 _iv("TESTEO_AISLAMIENTO", params={"retraso_dias": 1})])),
    "testeo_sin_retraso": ("Testeo sin retraso.",
                           _escenario(intervenciones=[
                               _iv("TESTEO_AISLAMIENTO", params={"deteccion": 0.5})])),
    "testeo_aislamiento_invalido": ("Dias de aislamiento en cero.",
                                    _escenario(intervenciones=[
                                        _iv("TESTEO_AISLAMIENTO",
                                            params={"deteccion": 0.5, "retraso_dias": 1,
                                                    "dias_aislamiento": 0})])),
    "testeo_sin_periodo_infeccioso": ("Testeo cuando falta infeccioso_dias.",
                                      _escenario(enfermedad=_enfermedad(quita=("infeccioso_dias",)),
                                                 intervenciones=[_iv(
                                                     "TESTEO_AISLAMIENTO",
                                                     params={"deteccion": 0.5,
                                                             "retraso_dias": 1})])),
    "vacuna_sin_eficacia": ("Vacunacion sin eficacia.",
                            _escenario(intervenciones=[
                                _iv("VACUNACION", params={"dosis_diarias": 100})])),
    "vacuna_sin_dosis": ("Vacunacion sin dosis diarias enteras.",
                         _escenario(intervenciones=[
                             _iv("VACUNACION", params={"eficacia": 0.8,
                                                       "dosis_diarias": 2.5})])),
    "vacuna_edad_desc_sin_grupos": ("Prioridad por edad con poblacion total.",
                                    _escenario(intervenciones=[
                                        _iv("VACUNACION", params={
                                            "eficacia": 0.8, "dosis_diarias": 100,
                                            "prioridad": "edad_desc"})])),
    "vacuna_edad_minima_fuera_de_rango": ("Edad minima mayor que 120.",
                                          _escenario(poblacion=POR_EDAD, intervenciones=[
                                              _iv("VACUNACION", params={
                                                  "eficacia": 0.8, "dosis_diarias": 100,
                                                  "edad_minima": 150})])),
    "vacuna_edad_minima_sin_grupos": ("Edad minima con poblacion total.",
                                      _escenario(intervenciones=[
                                          _iv("VACUNACION", params={
                                              "eficacia": 0.8, "dosis_diarias": 100,
                                              "edad_minima": 60})])),
    "vacuna_edad_minima_sin_grupo_que_empiece": ("Ningun grupo empieza en esa edad o despues.",
                                                 _escenario(poblacion=POR_EDAD, intervenciones=[
                                                     _iv("VACUNACION", params={
                                                         "eficacia": 0.8, "dosis_diarias": 100,
                                                         "edad_minima": 70})])),
    "muchos_errores_a_la_vez": (
        "Errores de todos los bloques juntos: fija el ORDEN en que se reportan.",
        _escenario(poblacion={"0-19": 100, "x": 5}, dias=5000, infectados_iniciales=0,
                   enfermedad=_enfermedad(quita=("r0",), letalidad=3,
                                          tasa_hospitalizacion="mucha"),
                   capas_contacto={"hogar": 2},
                   intervenciones=[_iv("CUBREBOCAS", inicio=-1), _iv("NADA"),
                                   _iv("VACUNACION", params={"eficacia": 2})])),
    # Valores que llegan con otro tipo de JSON: antes reventaban con TypeError o
    # AttributeError en vez de dar un error de validacion (LIMP-16).
    "intervenciones_no_es_lista": ("intervenciones es un numero.",
                                   _escenario(intervenciones=5)),
    "intervenciones_es_texto": ("intervenciones es un texto: un solo error, no uno por letra.",
                                _escenario(intervenciones="CUBREBOCAS")),
    "intervencion_tipo_no_textual": ("El tipo llega como lista.",
                                     _escenario(intervenciones=[{"tipo": ["CUBREBOCAS"],
                                                                 "dia_inicio": 0}])),
    "intervencion_params_no_objeto": ("params llega como lista.",
                                      _escenario(intervenciones=[_iv("CUBREBOCAS",
                                                                     params=[0.3])])),
    "politica_no_textual": ("La politica de edad desconocida llega como objeto.",
                            _escenario(poblacion=POR_EDAD, poblacion_edad_desconocida=100,
                                       politica_edad_desconocida={"excluir": True})),
}
