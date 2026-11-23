import unittest
from unittest.mock import patch

from frontend_web.app import seguridad


def img_src(env):
    with patch.dict("os.environ", env):
        politica = seguridad.csp()
    return next(p for p in politica.split("; ") if p.startswith("img-src"))


class CspDelBucket(unittest.TestCase):
    def test_con_el_emulador_el_origen_de_las_urls_firmadas_entra_al_img_src(self):
        self.assertEqual(img_src({"BUCKET_URL_PUBLICA": "http://localhost:4443/"}),
                         "img-src 'self' data: https: http://localhost:4443")

    def test_en_gcp_va_vacia_y_no_se_agrega_nada(self):
        self.assertEqual(img_src({"BUCKET_URL_PUBLICA": ""}), "img-src 'self' data: https:")

    def test_un_valor_que_no_es_una_url_no_entra_al_encabezado(self):
        for valor in ("javascript:alert(1)", "*", "http://", "localhost:4443; script-src *"):
            self.assertEqual(img_src({"BUCKET_URL_PUBLICA": valor}), "img-src 'self' data: https:")

    def test_el_resto_de_la_politica_no_cambia(self):
        with patch.dict("os.environ", {"BUCKET_URL_PUBLICA": "http://localhost:4443"}):
            politica = seguridad.csp()
        self.assertIn("script-src 'self' 'unsafe-inline' https://code.highcharts.com", politica)
        self.assertIn("frame-ancestors 'none'", politica)
        self.assertIn("object-src 'none'", politica)
