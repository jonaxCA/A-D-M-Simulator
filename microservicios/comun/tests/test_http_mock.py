from pathlib import Path

import pytest


def _app(monkeypatch):
    pytest.importorskip('flask')
    pytest.importorskip('redis')
    pytest.importorskip('psycopg2')
    from epidemia_comun.fabrica import crear_app
    from epidemia_comun.formatos import responder, leer_cuerpo
    from epidemia_comun.errores import ErrorAPI
    monkeypatch.setenv('JWT_SECRET_KEY', 'solo-para-pruebas-locales-no-usar-en-despliegue')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/15')
    documento = Path(__file__).resolve().parents[3]/'docs/contratos/regiones/openapi.json'
    def rutas(app):
        @app.get('/api/v1/example')
        def ejemplo():
            return responder({'population': 100, 'region': 'Prueba'}, 'ejemplo')
        @app.post('/api/v1/example')
        def escribir():
            datos = leer_cuerpo()
            return responder(datos, 'ejemplo', estado=201)
        @app.get('/api/v1/bad')
        def bad():
            raise ErrorAPI(404, 'NO_ENCONTRADO', 'No existe')
    return crear_app('regiones', documento, rutas)


def test_servidor_responde_xml_y_json(monkeypatch):
    app = _app(monkeypatch)
    client = app.test_client()
    xml = client.get('/api/v1/example')
    assert xml.status_code == 200 and xml.content_type.startswith('application/xml')
    assert b'<population tipo="numero">100</population>' in xml.data
    response = client.get('/api/v1/example?format=json')
    assert response.json['population'] == 100
    assert response.headers['X-Correlation-ID']


def test_formato_invalido_error_controlado(monkeypatch):
    client = _app(monkeypatch).test_client()
    res = client.get('/api/v1/example?format=yaml')
    assert res.status_code == 400 and b'DATOS_INVALIDOS' in res.data


def test_json_y_xml_peticiones(monkeypatch):
    client = _app(monkeypatch).test_client()
    r = client.post('/api/v1/example?format=json', json={'poblacion':5})
    assert r.status_code == 201 and r.json['poblacion'] == 5
    r2 = client.post('/api/v1/example?format=json', data='<ejemplo><poblacion tipo="numero">5</poblacion></ejemplo>', content_type='application/xml')
    assert r2.status_code == 201 and r2.json['poblacion'] == 5


def test_errores_problem_json_y_openapi(monkeypatch):
    client = _app(monkeypatch).test_client()
    error = client.get('/api/v1/bad?format=json')
    assert error.status_code == 404 and error.json['codigo'] == 'NO_ENCONTRADO'
    assert client.get('/openapi.json').json['info']['version'] == '0.1.0'
    assert client.get('/docs').status_code == 200
