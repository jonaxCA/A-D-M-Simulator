"""El límite de consumo (D31) en los contenedores reales: 429 con Retry-After y se libera al vencer."""
import time


def test_login_pasa_el_limite_da_429_y_se_libera(api):
    ruta = "/api/v1/auth/login"
    cuerpo = {"usuario": "nadie", "password": "x", "captcha_id": "x", "captcha_respuesta": "x"}
    respuestas = [api("auth", "POST", ruta, json=cuerpo) for _ in range(11)]
    limitada = respuestas[-1]
    assert limitada.status_code == 429, [r.status_code for r in respuestas]
    assert limitada.json()["codigo"] == "LIMITE_EXCEDIDO"
    espera = int(limitada.headers["Retry-After"])
    assert 0 < espera <= 60
    time.sleep(espera + 1)
    assert api("auth", "POST", ruta, json=cuerpo).status_code != 429
