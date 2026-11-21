"""
Volumen de datos (D29): llena series_corridas con corridas del SEIR y mide.

Genera VERSIONES x REPLICAS corridas de DIAS días (por omisión 100 x 100 x 180: 10,000
corridas, 1.81 millones de documentos) con seir-ref y las mismas funciones que usan el simulador
y resultados (microservicios.simulador.serie y microservicios.resultados.serie). Cada versión cambia la R0 del escenario de ejemplo
del contrato del motor, cuyos parámetros son supuestos; cada réplica, la semilla.

Mide: inserción con y sin índices, la serie de una corrida y la banda p5-p95 con y sin su
índice, la serie con y sin la caché de Redis, y CPU, memoria y disco del contenedor de MongoDB.
Imprime los resultados en Markdown (docs/pruebas/volumen/).

Escribe en la base de MONGO_URL, que tiene que ser epidemia_pruebas: borra su series_corridas
al empezar y se niega a correr contra la de la demostración. Necesita REDIS_URL. Desde la raíz:

  MONGO_URL="mongodb://epidemia:<MONGO_PASSWORD>@127.0.0.1:27018/epidemia_pruebas?authSource=epidemia" \
  REDIS_URL="redis://:<REDIS_PASSWORD>@127.0.0.1:6380/0" \
  python datos/scripts/volumen_mongo.py > docs/pruebas/volumen/<fecha>/resultados.md
"""
import argparse
import copy
import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "microservicios" / "comun")]

from epidemia_comun import cache, mongo, redis_compartido  # noqa: E402
from microservicios.resultados import serie as lee  # noqa: E402
from microservicios.simulador import serie as escribe  # noqa: E402
from procesamiento.contrato import ESCENARIO_EJEMPLO  # noqa: E402
from procesamiento.motor import simular  # noqa: E402

MOTOR = "seir-ref"
COMPOSE = RAIZ / "infra" / "docker-compose.yml"


def avance(texto):
    print(texto, file=sys.stderr, flush=True)


def corridas(version, replicas, dias):
    escenario = copy.deepcopy(ESCENARIO_EJEMPLO)
    escenario["dias"] = dias
    escenario["enfermedad"]["r0"]["valor"] = round(1.2 + 0.01 * version, 2)
    for r in range(replicas):
        run_id = version * replicas + r + 1
        # D8: cada réplica es su propio lote. Cada versión es su propio escenario; desde D5 del
        # checklist, cada documento de series_corridas lleva scenario_id.
        run = {"id": run_id, "batch_id": run_id, "scenario_id": version + 1,
               "scenario_version_id": version + 1, "seed": run_id}
        yield escribe.documentos(run, MOTOR, simular(escenario, run_id))


class Recursos(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.contenedor = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE), "ps", "-q", "mongodb"],
            capture_output=True, text=True).stdout.strip()
        self.cpu, self.memoria, self.disco, self.alto = [], [], "", threading.Event()

    def run(self):
        while self.contenedor and not self.alto.is_set():
            salida = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{json .}}", self.contenedor],
                capture_output=True, text=True).stdout
            if salida:
                datos = json.loads(salida)
                self.cpu.append(float(datos["CPUPerc"].rstrip("%")))
                self.memoria.append(datos["MemUsage"].split("/")[0].strip())
                self.disco = datos["BlockIO"]

    def resumen(self):
        self.alto.set()
        if not self.cpu:
            return "sin muestras de docker stats (¿está levantado el mongodb del compose?)"
        return ("CPU media %.0f %%, máxima %.0f %%; memoria al final %s; disco leído / escrito desde que arrancó %s"
                " (%d muestras)" % (statistics.mean(self.cpu), max(self.cpu), self.memoria[-1],
                                    self.disco, len(self.cpu)))


def mediana_ms(funcion, argumentos):
    tiempos = []
    for a in argumentos:
        inicio = time.perf_counter()
        funcion(a)
        tiempos.append((time.perf_counter() - inicio) * 1000)
    return statistics.median(tiempos)


def sin_indice(col, campos, funcion, argumentos):
    nombre = "_".join("%s_%s" % c for c in campos)
    opciones = next(o for c, o in mongo.INDICES[escribe.COLECCION] if c == campos)
    col.drop_index(nombre)
    try:
        return mediana_ms(funcion, argumentos)
    finally:
        inicio = time.perf_counter()
        col.create_index(campos, **opciones)
        avance("índice %s reconstruido en %.1f s" % (nombre, time.perf_counter() - inicio))


def principal():
    argumentos = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    argumentos.add_argument("--versiones", type=int, default=100)
    argumentos.add_argument("--replicas", type=int, default=100)
    argumentos.add_argument("--dias", type=int, default=180)
    argumentos.add_argument("--muestras", type=int, default=20)
    opciones = argumentos.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    base = mongo.base()
    if base.name == "epidemia":
        sys.exit("MONGO_URL apunta a la base de la demostración: usa epidemia_pruebas.")
    redis_compartido.cliente().ping()
    base.drop_collection(escribe.COLECCION)
    base.drop_collection("series_sin_indices")
    col = mongo.coleccion(escribe.COLECCION)
    versiones, replicas = opciones.versiones, opciones.replicas

    # La inserción con índices, de todo el volumen; sin índices, de las primeras versiones.
    recursos = Recursos()
    recursos.start()
    inicio_total, insercion, sin_indices, docs_sin = time.perf_counter(), 0.0, 0.0, 0
    for v in range(versiones):
        docs = [d for serie in corridas(v, replicas, opciones.dias) for d in serie]
        inicio = time.perf_counter()
        col.insert_many(docs, ordered=False)
        insercion += time.perf_counter() - inicio
        if v < max(1, versiones // 10):
            for d in docs:
                d.pop("_id")
            inicio = time.perf_counter()
            base["series_sin_indices"].insert_many(docs, ordered=False)
            sin_indices += time.perf_counter() - inicio
            docs_sin += len(docs)
        avance("versión %d de %d" % (v + 1, versiones))
    total = time.perf_counter() - inicio_total
    uso = recursos.resumen()
    base.drop_collection("series_sin_indices")
    estadisticas = base.command("collStats", escribe.COLECCION)

    # El simulador guarda con replace_one por día (serie.guardar): una corrida.
    muestra = next(corridas(versiones, 1, opciones.dias))
    inicio = time.perf_counter()
    escribe.guardar(muestra)
    guardar_ms = (time.perf_counter() - inicio) * 1000
    col.delete_many({"run_id": muestra[0]["run_id"]})

    n = opciones.muestras
    total_corridas = versiones * replicas
    run_ids = [1 + (i * 7919) % total_corridas for i in range(n)]
    version_ids = [1 + (i * 31) % versiones for i in range(n)]
    serie = lambda r: lee.leer(r)
    banda = lambda v: lee.banda(v, MOTOR)
    serie_con = mediana_ms(serie, run_ids)
    serie_sin = sin_indice(col, [("run_id", 1), ("dia", 1)], serie, run_ids)
    banda_con = mediana_ms(banda, version_ids)
    banda_sin = sin_indice(col, [("scenario_version_id", 1), ("motor", 1), ("dia", 1)], banda, version_ids)

    # Lo mismo que resultados (_serie), con otro prefijo para no tocar su caché.
    def con_cache(r):
        return cache.obtener("volumen", "serie=%d" % r, 300, lambda: lee.leer(r))

    llaves = ["cache:volumen:serie=%d" % r for r in run_ids]
    redis_compartido.cliente().delete(*llaves)
    fallo = mediana_ms(con_cache, run_ids)
    acierto = mediana_ms(con_cache, run_ids)
    redis_compartido.cliente().delete(*llaves)

    mb = 1024 * 1024
    print("| Medición | Resultado |")
    print("|---|---|")
    print("| Volumen | %d corridas de %d días: %d documentos en %d versiones |"
          % (total_corridas, opciones.dias, estadisticas["count"], versiones))
    print("| Tiempo total (simular e insertar) | %.0f s |" % total)
    print("| Inserción con los dos índices (`insert_many`) | %.1f s, %.0f documentos/s |"
          % (insercion, estadisticas["count"] / insercion))
    print("| Inserción sin índices (%d documentos) | %.1f s, %.0f documentos/s |"
          % (docs_sin, sin_indices, docs_sin / sin_indices))
    print("| Una corrida como la guarda el simulador (`guardar`, %d `replace_one`) | %.0f ms |"
          % (len(muestra), guardar_ms))
    print("| Serie de una corrida (`leer`), con `{run_id, dia}` | %.1f ms |" % serie_con)
    print("| Serie de una corrida, sin índice | %.1f ms |" % serie_sin)
    print("| Banda p5-p95 de una versión (`banda`), con `{scenario_version_id, motor, dia}` | %.1f ms |"
          % banda_con)
    print("| Banda p5-p95, sin índice | %.1f ms |" % banda_sin)
    print("| Serie sin caché (Redis vacío: lee MongoDB y guarda) | %.1f ms |" % fallo)
    print("| Serie con caché (Redis) | %.1f ms |" % acierto)
    print("| Disco: datos / comprimido / índices | %.0f MB / %.0f MB / %.0f MB |"
          % (estadisticas["size"] / mb, estadisticas["storageSize"] / mb,
             estadisticas["totalIndexSize"] / mb))
    print("| Contenedor de MongoDB durante la carga | %s |" % uso)
    print()
    print("Medianas de %d consultas distintas. Sin índice, MongoDB recorre la colección completa." % n)


if __name__ == "__main__":
    principal()
