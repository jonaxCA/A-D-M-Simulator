"""Formularios por enfermedad, con versiones (D48, F7).

Los campos fijos del caso se quedan como están; cada enfermedad suma los suyos en un formulario.
Una versión nace borrador, se edita y se publica; publicada ya no cambia. Al publicar otra, la
anterior pasa a retirado y sigue valiendo para los casos capturados con ella sin conexión.

Aquí van: la validación de un formulario (definicion), la de las respuestas de un caso
(respuestas) y el acceso a case_forms. rutas.py los usa.
"""
import json
import math
import re
from datetime import date

import psycopg2.extras

from epidemia_comun.bd import get_conn, query
from epidemia_comun.errores import ErrorAPI

TIPOS = ("texto", "entero", "decimal", "fecha", "booleano", "opcion", "opciones")
CLAVE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
MAXIMO_CAMPOS = 60
MAXIMO_OPCIONES = 50
TEXTO_POR_OMISION, TEXTO_MAXIMO = 500, 2000
TITULO_MAXIMO = 160
# Las claves de los campos fijos del caso: un campo del formulario no se llama igual.
RESERVADAS = {"local_uuid", "device_id", "disease_id", "region_id", "report_date", "onset_date",
              "age", "sex", "latitude", "longitude", "test_result", "severity", "status",
              "form_id", "form_answers", "reason"}
COLUMNAS = ("id", "disease_id", "version", "status", "title", "fields", "required", "created_by",
            "created_at", "updated_at", "published_by", "published_at")


# ------------------------------------------------------------------ la definición

def _texto(valor, nombre, maximo, obligatorio=True):
    if valor is None and not obligatorio:
        return None
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError("%s es obligatorio y es texto." % nombre)
    if len(valor.strip()) > maximo:
        raise ValueError("%s no puede pasar de %d caracteres." % (nombre, maximo))
    return valor.strip()


def _numero(valor, nombre, entero):
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError("%s debe ser un número." % nombre)
    if entero and int(valor) != valor:
        raise ValueError("%s debe ser entero." % nombre)
    return int(valor) if entero else valor


def _campo(crudo, i):
    if not isinstance(crudo, dict):
        raise ValueError("El campo %d debe ser un objeto." % (i + 1))
    desconocidos = set(crudo) - {"clave", "etiqueta", "tipo", "obligatorio", "minimo", "maximo",
                                 "max_largo", "opciones", "ayuda"}
    if desconocidos:
        raise ValueError("El campo %d trae atributos desconocidos: %s." % (i + 1, ", ".join(sorted(desconocidos))))
    clave = crudo.get("clave")
    if not isinstance(clave, str) or not CLAVE.match(clave):
        raise ValueError("La clave del campo %d debe empezar con minúscula y llevar solo minúsculas, "
                         "dígitos y guiones bajos (hasta 40)." % (i + 1))
    if clave in RESERVADAS:
        raise ValueError("%s es un campo fijo del caso: el formulario no lo repite." % clave)
    tipo = crudo.get("tipo")
    if tipo not in TIPOS:
        raise ValueError("%s: tipo debe ser uno de %s." % (clave, ", ".join(TIPOS)))
    obligatorio = crudo.get("obligatorio", False)
    if not isinstance(obligatorio, bool):
        raise ValueError("%s: obligatorio es true o false." % clave)
    campo = {"clave": clave, "etiqueta": _texto(crudo.get("etiqueta"), clave + ": etiqueta", 120),
             "tipo": tipo, "obligatorio": obligatorio}
    ayuda = _texto(crudo.get("ayuda"), clave + ": ayuda", 300, obligatorio=False)
    if ayuda:
        campo["ayuda"] = ayuda
    if tipo in ("entero", "decimal"):
        minimo = _numero(crudo.get("minimo"), clave + ": minimo", tipo == "entero")
        maximo = _numero(crudo.get("maximo"), clave + ": maximo", tipo == "entero")
        if minimo is not None and maximo is not None and minimo > maximo:
            raise ValueError("%s: minimo no puede pasar de maximo." % clave)
        campo.update({k: v for k, v in (("minimo", minimo), ("maximo", maximo)) if v is not None})
    elif any(k in crudo for k in ("minimo", "maximo")):
        raise ValueError("%s: minimo y maximo solo van con entero o decimal." % clave)
    if tipo == "texto":
        largo = crudo.get("max_largo", TEXTO_POR_OMISION)
        if isinstance(largo, bool) or not isinstance(largo, int) or not 1 <= largo <= TEXTO_MAXIMO:
            raise ValueError("%s: max_largo va de 1 a %d." % (clave, TEXTO_MAXIMO))
        campo["max_largo"] = largo
    elif "max_largo" in crudo:
        raise ValueError("%s: max_largo solo va con texto." % clave)
    if tipo in ("opcion", "opciones"):
        opciones = crudo.get("opciones")
        if not isinstance(opciones, list) or not 2 <= len(opciones) <= MAXIMO_OPCIONES:
            raise ValueError("%s: opciones es una lista de 2 a %d." % (clave, MAXIMO_OPCIONES))
        limpias = []
        for o in opciones:
            if not isinstance(o, dict) or set(o) - {"valor", "etiqueta"}:
                raise ValueError("%s: cada opción es {valor, etiqueta}." % clave)
            valor = o.get("valor")
            if not isinstance(valor, str) or not CLAVE.match(valor):
                raise ValueError("%s: el valor de una opción va como una clave (minúsculas, dígitos, _)." % clave)
            limpias.append({"valor": valor, "etiqueta": _texto(o.get("etiqueta"), clave + ": etiqueta de opción", 120)})
        if len({o["valor"] for o in limpias}) != len(limpias):
            raise ValueError("%s: dos opciones con el mismo valor." % clave)
        campo["opciones"] = limpias
    elif "opciones" in crudo:
        raise ValueError("%s: opciones solo va con opcion u opciones." % clave)
    return campo


def definicion(cuerpo, parcial=False):
    """{title, fields, required} limpio de lo que manda quien edita; 422 con el motivo.
    Con parcial, solo lo que venga (para reemplazar un borrador también se manda todo)."""
    if not isinstance(cuerpo, dict):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El formulario debe ser un objeto.")
    try:
        campos = cuerpo.get("fields")
        if not isinstance(campos, list) or not 1 <= len(campos) <= MAXIMO_CAMPOS:
            raise ValueError("fields es una lista de 1 a %d campos." % MAXIMO_CAMPOS)
        limpios = [_campo(c, i) for i, c in enumerate(campos)]
        repetidas = sorted({c["clave"] for c in limpios if [d["clave"] for d in limpios].count(c["clave"]) > 1})
        if repetidas:
            raise ValueError("Claves repetidas: %s." % ", ".join(repetidas))
        requerido = cuerpo.get("required", False)
        if not isinstance(requerido, bool):
            raise ValueError("required es true o false.")
        return {"title": _texto(cuerpo.get("title"), "title", TITULO_MAXIMO), "fields": limpios,
                "required": requerido}
    except ValueError as exc:
        raise ErrorAPI(422, "DATOS_INVALIDOS", str(exc))


# ------------------------------------------------------------------ las respuestas

def _lista(valor):
    # En XML, <sintomas><item>fiebre</item>...</sintomas> llega como {"item": ... }.
    if isinstance(valor, dict) and set(valor) == {"item"}:
        valor = valor["item"]
        return valor if isinstance(valor, list) else [valor]
    return valor


def _respuesta(campo, valor):
    tipo, clave = campo["tipo"], campo["clave"]
    if tipo == "texto":
        if not isinstance(valor, str):
            raise ValueError("%s es texto." % clave)
        if len(valor) > campo["max_largo"]:
            raise ValueError("%s no puede pasar de %d caracteres." % (clave, campo["max_largo"]))
        return valor
    if tipo in ("entero", "decimal"):
        # Un XML trae el número como texto.
        if isinstance(valor, str):
            try:
                valor = int(valor) if tipo == "entero" else float(valor)
            except ValueError:
                raise ValueError("%s es un número%s." % (clave, " entero" if tipo == "entero" else ""))
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
            raise ValueError("%s es un número." % clave)
        if tipo == "entero":
            if int(valor) != valor:
                raise ValueError("%s es un número entero." % clave)
            valor = int(valor)
        if "minimo" in campo and valor < campo["minimo"] or "maximo" in campo and valor > campo["maximo"]:
            raise ValueError("%s va de %s a %s." % (clave, campo.get("minimo", "-∞"), campo.get("maximo", "∞")))
        return valor
    if tipo == "fecha":
        try:
            return date.fromisoformat(valor).isoformat()
        except (TypeError, ValueError):
            raise ValueError("%s es una fecha AAAA-MM-DD." % clave)
    if tipo == "booleano":
        if isinstance(valor, str) and valor in ("true", "false"):
            return valor == "true"
        if not isinstance(valor, bool):
            raise ValueError("%s es true o false." % clave)
        return valor
    validos = [o["valor"] for o in campo["opciones"]]
    if tipo == "opcion":
        if valor not in validos:
            raise ValueError("%s debe ser una de: %s." % (clave, ", ".join(validos)))
        return valor
    valor = _lista(valor)
    if not isinstance(valor, list) or any(v not in validos for v in valor) or len(set(valor)) != len(valor):
        raise ValueError("%s es una lista sin repetir de: %s." % (clave, ", ".join(validos)))
    return [v for v in validos if v in valor]  # en el orden del formulario


def respuestas(formulario, crudas):
    """Las respuestas validadas contra una versión del formulario: {clave: valor} sin los campos
    vacíos. 422 con todos los motivos juntos."""
    if not isinstance(crudas, dict):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "form_answers debe ser un objeto {clave: valor}.")
    campos = {c["clave"]: c for c in formulario["fields"]}
    errores = ["%s no es un campo del formulario." % k for k in sorted(set(crudas) - set(campos))]
    limpias = {}
    for clave, campo in campos.items():
        valor = crudas.get(clave)
        vacio = valor is None or valor == "" or _lista(valor) == []
        if vacio:
            if campo["obligatorio"]:
                errores.append("%s es obligatorio." % clave)
            continue
        try:
            limpias[clave] = _respuesta(campo, valor)
        except ValueError as exc:
            errores.append(str(exc))
    if errores:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Formulario (versión %d): %s"
                       % (formulario["version"], " ".join(errores)))
    return limpias


def para_caso(formulario, disease_id):
    """La versión con que se captura un caso: de su enfermedad y publicada o retirada."""
    if formulario is None:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "form_id no es un formulario que exista.")
    if formulario["disease_id"] != disease_id:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El formulario %d es de otra enfermedad." % formulario["id"])
    if formulario["status"] == "borrador":
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El formulario %d es un borrador: no se captura con él."
                       % formulario["id"])
    return formulario


# ------------------------------------------------------------------ la base

def por_id(form_id):
    fila = query("SELECT " + ", ".join(COLUMNAS) + " FROM case_forms WHERE id = %s", (form_id,), one=True)
    return dict(fila) if fila else None


def lista(disease_id=None, estado=None):
    condiciones, params = [], []
    if disease_id is not None:
        condiciones.append("disease_id = %s")
        params.append(disease_id)
    if estado is not None:
        condiciones.append("status = %s")
        params.append(estado)
    donde = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return [dict(f) for f in query("SELECT " + ", ".join(COLUMNAS) + " FROM case_forms" + donde
                                   + " ORDER BY disease_id, version", tuple(params))]


def vigentes(disease_id=None):
    return lista(disease_id, "publicado")


def crea_borrador(disease_id, datos, usuario):
    """La versión siguiente de la enfermedad, en borrador. 409 si ya tiene uno."""
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT id FROM diseases WHERE id = %s", (disease_id,))
                if cur.fetchone() is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
                cur.execute("""INSERT INTO case_forms (disease_id, version, title, fields, required, created_by)
                               SELECT %s, coalesce(max(version), 0) + 1, %s, %s::jsonb, %s, %s
                               FROM case_forms WHERE disease_id = %s
                               RETURNING """ + ", ".join(COLUMNAS),
                            (disease_id, datos["title"], json.dumps(datos["fields"], ensure_ascii=False),
                             datos["required"], usuario, disease_id))
                nuevo = dict(cur.fetchone())
            conn.commit()
    except psycopg2.errors.UniqueViolation as exc:
        raise ErrorAPI(409, "CONFLICTO", "Esa enfermedad ya tiene un borrador: edítalo o publícalo.") from exc
    return nuevo


def reemplaza_borrador(form_id, datos):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""UPDATE case_forms SET title = %s, fields = %s::jsonb, required = %s,
                                  updated_at = now()
                           WHERE id = %s AND status = 'borrador'
                           RETURNING """ + ", ".join(COLUMNAS),
                        (datos["title"], json.dumps(datos["fields"], ensure_ascii=False),
                         datos["required"], form_id))
            fila = cur.fetchone()
            if fila is None:
                cur.execute("SELECT status FROM case_forms WHERE id = %s", (form_id,))
                existe = cur.fetchone()
                if existe is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el formulario.")
                raise ErrorAPI(409, "CONFLICTO", "El formulario %d ya está %s: no cambia; crea otro borrador."
                               % (form_id, existe["status"]))
        conn.commit()
    return dict(fila)


def publica(form_id, usuario):
    """El borrador pasa a publicado y la versión vigente de la enfermedad, a retirado; las dos
    en la misma transacción."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT disease_id, status FROM case_forms WHERE id = %s FOR UPDATE", (form_id,))
            actual = cur.fetchone()
            if actual is None:
                raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el formulario.")
            if actual["status"] != "borrador":
                raise ErrorAPI(409, "CONFLICTO", "El formulario %d ya está %s." % (form_id, actual["status"]))
            cur.execute("UPDATE case_forms SET status = 'retirado' WHERE disease_id = %s AND status = 'publicado'",
                        (actual["disease_id"],))
            cur.execute("""UPDATE case_forms SET status = 'publicado', published_by = %s, published_at = now()
                           WHERE id = %s RETURNING """ + ", ".join(COLUMNAS), (usuario, form_id))
            publicado = dict(cur.fetchone())
        conn.commit()
    return publicado
