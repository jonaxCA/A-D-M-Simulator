"""
Pruebas de integracion HTTP de /auditoria (Flask test client contra
PostgreSQL real), especificas del bug de UAT: "abro la bitacora como admin
y no aparecen los eventos de las corridas: solicitada, ejecutando, completada
y fallida". La causa era de presentacion, no de escritura -- las 4 etapas SI
llegaban a audit_log (accion RUN + data_after['estado']), pero
get_auditoria_lista() las mostraba todas igual ("Ejecucion"/"Correcto",
incluida la fallida). Ver backend_web/tests/test_auditoria.py para las
pruebas de la funcion pura; este archivo confirma el HTML que de verdad
recibe el admin.

Nota de acentos: las descripciones que arma backend_web.queries (igual que
DESCRIPCION_POR_ACCION ya existente, p.ej. "Inicio de sesion exitoso") van
SIN acentos -- es la convencion que ya tenia ese diccionario antes de este
cambio. Lo que si tiene acentos es el texto fijo de la plantilla
(auditoria.html: "Bitácora", "Acción", etc.), que este archivo no toca.

Ejecutar:
    DATABASE_URL=postgresql://epidemia_app:epidemia_app_pw@localhost:5432/simulador_epidemico \
    JWT_SECRET_KEY=test-secret \
        python -m unittest frontend_web.tests.test_auditoria_rutas -v
"""
import unittest

from frontend_web.tests.base import RutasConCorridas


class AuditoriaRutasTests(RutasConCorridas):
    def test_bitacora_muestra_las_4_etapas_de_una_corrida_real(self):
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            resp = client.post(f"/simulaciones/{self.version_id}/ejecutar",
                               data={"seed": "77001"}, follow_redirects=False)
            run_id = self._run_id_del_redirect(resp)
            self._batches_creados.append(self._batch_del_run(run_id))
            self._espera_terminal(client, run_id)

        sim_id = f"SIM-{run_id:05d}"
        with self.app.test_client() as client:
            self._login(client, "admin", "Admin2026!")
            resp = client.get("/auditoria")
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode("utf-8")
            self.assertIn(f"Simulacion solicitada {sim_id}", html)
            self.assertIn(f"Simulacion en ejecucion (inicio) {sim_id}", html)
            self.assertIn(f"Simulacion completada {sim_id}", html)

    def test_bitacora_muestra_corrida_fallida_forzada_como_fallida_no_correcta(self):
        with self.app.test_client() as client:
            self._login(client, "admin", "Admin2026!")
            resp = client.post(f"/simulaciones/{self.version_id}/ejecutar",
                               data={"seed": "77002", "forzar_error": "1"}, follow_redirects=False)
            run_id = self._run_id_del_redirect(resp)
            self._batches_creados.append(self._batch_del_run(run_id))
            self._espera_terminal(client, run_id)

            resp = client.get("/auditoria")
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode("utf-8")
            sim_id = f"SIM-{run_id:05d}"
            self.assertIn(f"Simulacion fallida {sim_id}: Error forzado de prueba", html)
            # El badge de estado de ESTA fila debe leerse "Fallido", no
            # "Correcto" -- ese fue el bug reportado ("no aparecen ...
            # fallida"): la corrida SI aparecia, pero maquillada de exitosa.
            fila_html = html.split(f"Simulacion fallida {sim_id}")[1][:400]
            self.assertIn("Fallido", fila_html)

    def test_bitacora_rechaza_a_quien_no_es_administrador(self):
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            resp = client.get("/auditoria", follow_redirects=False)
            self.assertEqual(resp.status_code, 302)

    def test_filtro_de_accion_incluye_las_etapas_de_simulacion(self):
        with self.app.test_client() as client:
            self._login(client, "admin", "Admin2026!")
            resp = client.get("/auditoria")
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode("utf-8")
            self.assertIn('value="RUN::fallido"', html)
            self.assertIn('value="RUN::completado"', html)

    def test_filtro_run_fallido_aisla_solo_las_fallidas_de_esa_corrida(self):
        with self.app.test_client() as client:
            self._login(client, "admin", "Admin2026!")

            resp = client.post(f"/simulaciones/{self.version_id}/ejecutar",
                               data={"seed": "77003"}, follow_redirects=False)
            run_completado = self._run_id_del_redirect(resp)
            self._batches_creados.append(self._batch_del_run(run_completado))
            self._espera_terminal(client, run_completado)

            resp = client.post(f"/simulaciones/{self.version_id}/ejecutar",
                               data={"seed": "77004", "forzar_error": "1"}, follow_redirects=False)
            run_fallido = self._run_id_del_redirect(resp)
            self._batches_creados.append(self._batch_del_run(run_fallido))
            self._espera_terminal(client, run_fallido)

            resp = client.get("/auditoria?accion=RUN::fallido")
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode("utf-8")
            self.assertIn(f"SIM-{run_fallido:05d}", html.split("<tbody>")[1])
            # La corrida completada NO debe aparecer en el CUERPO de la
            # tabla filtrada (el <select> de Accion si puede listar la
            # etiqueta "Simulacion completada" como OPCION disponible --
            # por eso se compara solo dentro de <tbody>, no en toda la pagina).
            cuerpo_tabla = html.split("<tbody>")[1].split("</tbody>")[0]
            self.assertNotIn(f"SIM-{run_completado:05d}", cuerpo_tabla)


if __name__ == "__main__":
    unittest.main()
