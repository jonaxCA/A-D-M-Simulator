import ast
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / 'microservicios/comun'))

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import a_xml, de_xml
from epidemia_comun.validaciones import entero_positivo, diccionario


def test_xml_json_tipos_regresan_iguales():
    salida = de_xml(a_xml({'valor':3.15,'activo':True,'numero':9,'vacio':None}, 'datos'))
    assert salida == {'valor':3.15,'activo':True,'numero':9,'vacio':None}


def test_entero_positivo_rechaza_booleanos():
    for value in [True, False, 0, -1, 'texto', '3.7', '001']:
        with pytest.raises(ErrorAPI): entero_positivo(value)
    assert entero_positivo('3') == 3


def test_diccionario_no_acepta_lista():
    with pytest.raises(ErrorAPI): diccionario([])


@pytest.mark.parametrize('servicio,puerto', [('enfermedades',5211),('parametros',5212),('regiones',5213),('poblacion',5214)])
def test_contrato_y_dockerfile(servicio,puerto):
    contrato = json.loads((RAIZ / f'docs/contratos/{servicio}/openapi.json').read_text())
    assert contrato['openapi'] == '3.0.3'
    assert str(puerto) in contrato['servers'][0]['url']
    assert contrato['paths']
    for route, methods in contrato['paths'].items():
        for op, item in methods.items():
            assert {'get','post','put','patch','delete'} & {op}
            assert 'application/json' in item['responses'][next(iter(item['responses']))]['content']
            assert 'application/xml' in item['responses'][next(iter(item['responses']))]['content']
            if op in {'put','post'} and servicio != 'regiones':
                assert item.get('security') == [{'bearerAuth':[]}]
    docker = (RAIZ/f'microservicios/{servicio}/Dockerfile').read_text()
    assert f'microservicios.{servicio}.app:app' in docker
    assert 'HEALTHCHECK' in docker
    assert '/docs/contratos/' + servicio + '/' in docker


def test_rutas_contratos_coinciden():
    for servicio in ['enfermedades','parametros','regiones','poblacion']:
        contrato = json.loads((RAIZ / f'docs/contratos/{servicio}/openapi.json').read_text())
        programa = ast.parse((RAIZ / f'microservicios/{servicio}/rutas.py').read_text())
        rutas=set()
        for node in ast.walk(programa):
            if not isinstance(node,ast.FunctionDef):continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):continue
                if decorator.func.attr not in ('get','post','put','delete','patch'):continue
                if not decorator.args or not isinstance(decorator.args[0],ast.Constant): continue
                path = decorator.args[0].value
                path = __import__('re').sub(r'<int:([^>]+)>',r'{\1}',path)
                path = __import__('re').sub(r'<([^>]+)>',r'{\1}',path)
                if '{accion}' in path:
                    for verb in ['activate','deactivate']:
                        rutas.add((path.replace('{accion}',verb),decorator.func.attr))
                else:
                    rutas.add((path,decorator.func.attr))
        for route,methods in contrato['paths'].items():
            for verb in methods:
                assert (route,verb) in rutas,(servicio,route,verb)
        assert len(rutas) == sum(len(v) for v in contrato['paths'].values())
