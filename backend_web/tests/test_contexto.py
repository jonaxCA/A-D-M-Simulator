"""
La capa de datos sin Flask: quien hace la operacion y desde donde llegan en un
Contexto (backend_web/contexto.py), no de flask.request.

Estas pruebas no levantan la app ni simulan una peticion: si alguna funcion de
backend_web volviera a leer flask.request, fallarian con RuntimeError.

Ejecutar:
    python -m unittest backend_web.tests.test_contexto -v
"""
import unittest

from backend_web.tests.base import requiere_base, usuario_con_rol
from backend_web import queries
from backend_web.audit import log_audit
from backend_web.contexto import AGENTE_SIN_PETICION, Contexto
from backend_web.db import get_conn, query

NOMBRE = "ZZZ escenario de la prueba de contexto"
IP = "10.1.2.3"
NAVEGADOR = "navegador-de-prueba/1.0"


class ContextoTests(unittest.TestCase):
    def test_sin_peticion_no_tiene_ip_y_dice_por_que(self):
        contexto = Contexto.sin_peticion(7)
        self.assertEqual(contexto, Contexto(7, None, AGENTE_SIN_PETICION))

    def test_es_inmutable(self):
        with self.assertRaises(AttributeError):
            Contexto(7, IP, NAVEGADOR).user_id = 8


@requiere_base
class CapaDeDatosSinFlaskTests(unittest.TestCase):

    def setUp(self):
        self.autor = usuario_con_rol("ANALISTA") or usuario_con_rol("ADMINISTRADOR")
        self.contexto = Contexto(self.autor, IP, NAVEGADOR)
        self._borra()
        self.addCleanup(self._borra)

    def _borra(self):
        # audit_log no se toca: es de solo insercion.
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""DELETE FROM scenario_versions WHERE scenario_id IN
                               (SELECT id FROM scenarios WHERE name = %s)""", (NOMBRE,))
                cur.execute("DELETE FROM scenarios WHERE name = %s", (NOMBRE,))
            conn.commit()

    def _bitacora(self, entity_type, entity_id):
        return query(
            """SELECT user_id, host(ip_address) AS ip, user_agent FROM audit_log
               WHERE entity_type = %s AND entity_id = %s
               ORDER BY id DESC LIMIT 1""", (entity_type, str(entity_id)), one=True)

    def _crea_escenario(self):
        regiones = queries.get_regiones_para_escenario()
        enfermedades = queries.get_enfermedades_para_escenario()
        mty = next(r for r in regiones if r["code"] == "19039")
        enfermedad = next(e for e in enfermedades if e["simulable"])
        datos, errores = queries.valida_escenario(
            {"name": NOMBRE, "disease_id": str(enfermedad["id"]), "region_id": str(mty["id"]),
             "population_size": "1000", "initial_infected": "5", "horizon_days": "90"},
            regiones, enfermedades)
        self.assertEqual(errores, [])
        ok, error, sid = queries.crea_escenario(datos, contexto=self.contexto)
        self.assertTrue(ok, error)
        return sid

    def test_crear_un_escenario_audita_la_ip_y_el_navegador_del_contexto(self):
        sid = self._crea_escenario()
        fila = self._bitacora("scenarios", sid)
        self.assertEqual((fila["user_id"], fila["ip"], fila["user_agent"]),
                         (self.autor, IP, NAVEGADOR))

    def test_agregar_una_intervencion_tambien(self):
        sid = self._crea_escenario()
        detalle = queries.get_escenario_detalle(sid)
        datos, errores = queries.valida_intervencion(
            {"code": "CIERRE_ESCUELAS", "start_day": "10", "end_day": "60",
             "coverage": "1", "compliance": "0.9", "p_CIERRE_ESCUELAS_reduccion": "1"},
            queries.get_tipos_intervencion(), detalle["version"], detalle["intervenciones"])
        self.assertEqual(errores, [])
        ok, error = queries.agrega_intervencion(detalle["version"]["id"], datos,
                                                contexto=self.contexto)
        self.assertTrue(ok, error)
        iid = queries.get_escenario_detalle(sid)["intervenciones"][0]["id"]
        fila = self._bitacora("scenario_interventions", iid)
        self.assertEqual((fila["user_id"], fila["ip"], fila["user_agent"]),
                         (self.autor, IP, NAVEGADOR))

    def test_lo_que_corre_sin_peticion_queda_sin_ip(self):
        log_audit(Contexto.sin_peticion(self.autor), "RUN", "simulation_run",
                  entity_id="contexto-sin-peticion",
                  data_after={"estado": "encolado", "prueba": "test_contexto"})
        fila = self._bitacora("simulation_run", "contexto-sin-peticion")
        self.assertEqual((fila["user_id"], fila["ip"], fila["user_agent"]),
                         (self.autor, None, AGENTE_SIN_PETICION))
