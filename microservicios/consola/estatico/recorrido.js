"use strict";

// El recorrido de aceptación: los pasos del guion de docs/CHECKLIST_SEGUNDO_PARCIAL.md, listos
// para correr en orden. Cada paso recibe `h`, las herramientas de herramientas(): h.pide()
// hace la petición y la anota, h.espera() revisa el resultado y h.guarda() deja un id para los
// pasos siguientes. Los pasos de inicio de sesión los completa la persona: el captcha no se
// resuelve solo. Corre igual en la consola y en Node (globalThis.Recorrido).
(() => {
  const CUENTAS = {
    analista: {usuario: "alex.cavazos", rol: "ANALISTA", de: "de la analista"},
    epidemiologo: {usuario: "diana.flores", rol: "EPIDEMIOLOGO", de: "de la epidemióloga"},
    admin: {usuario: "admin", rol: "ADMINISTRADOR", de: "del administrador"},
  };
  const TERMINADAS = ["completado", "fallido", "cancelado"];
  const FUENTE_SUPUESTO = "Supuesto del recorrido de aceptación";
  const COMPOSE = "docker compose -f infra/docker-compose.yml";

  const hoy = () => new Date().toLocaleDateString("en-CA");
  const nuevoId = () => globalThis.crypto.randomUUID();
  const detalleDe = (r) => (r.datos && r.datos.detail ? `: ${r.datos.detail}` : "");

  function herramientas({urlDe, pide, sesiones, anota}) {
    const ctx = {};
    const h = {
      ctx,
      cuentas: CUENTAS,

      // formato: "json" (por omisión, con ?format=json) o null (sin ?format: XML, salvo
      // que accept pida otra cosa). cuenta: de quién es el token. silencioso: no se anota
      // (las consultas repetidas de h.hasta solo anotan la última).
      async pide(servicio, metodo, ruta, op = {}) {
        const consulta = new URLSearchParams(op.consulta || {});
        if ((op.formato === undefined ? "json" : op.formato) === "json") consulta.set("format", "json");
        const cabeceras = {};
        if (op.accept) cabeceras.Accept = op.accept;
        if (op.cuenta) cabeceras.Authorization = "Bearer " + h.sesion(op.cuenta).access;
        let cuerpo;
        if (op.json !== undefined) {
          cabeceras["Content-Type"] = "application/json";
          cuerpo = JSON.stringify(op.json);
        } else if (op.xml !== undefined) {
          cabeceras["Content-Type"] = "application/xml";
          cuerpo = op.xml;
        }
        const texto = consulta.toString();
        const camino = ruta + (texto ? "?" + texto : "");
        const {respuesta, texto: crudo, ms} = await pide(urlDe(servicio) + camino,
          {method: metodo, headers: cabeceras, body: cuerpo}, op.espera || 30000);
        const tipo = respuesta.headers.get("content-type") || "";
        let datos = null;
        if (/json/.test(tipo)) {
          try { datos = JSON.parse(crudo); } catch (e) { /* se queda el texto */ }
        }
        const r = {servicio, metodo, ruta: camino, estado: respuesta.status, tipo, texto: crudo, datos, ms,
                   correlacion: respuesta.headers.get("x-correlation-id")};
        h.ultima = r;
        if (!op.silencioso) anota({peticion: r});
        return r;
      },

      estado(r, ...codigos) {
        if (!codigos.includes(r.estado)) {
          throw new Error(`${r.metodo} ${r.servicio} ${r.ruta} respondió ${r.estado}${detalleDe(r)}; ` +
            `se esperaba ${codigos.join(" o ")}.`);
        }
      },

      espera(condicion, logro, falla) {
        if (!condicion) throw new Error(falla || "No se cumplió: " + logro);
        anota({bien: logro});
      },

      guarda(clave, valor) {
        ctx[clave] = valor;
        anota({guardado: [clave, valor]});
        return valor;
      },

      necesita(...claves) {
        for (const clave of claves) {
          if (ctx[clave] === undefined) throw new Error(`Falta ${clave}: corre antes el paso que lo guarda.`);
        }
      },

      sesion(cuenta) {
        if (!sesiones[cuenta]) {
          throw new Error(`Falta la sesión ${CUENTAS[cuenta].de}: corre antes su paso de inicio de sesión.`);
        }
        return sesiones[cuenta];
      },

      olvida(cuenta) { delete sesiones[cuenta]; },
      nota(texto) { anota({nota: texto}); },
      progreso(texto) { anota({progreso: texto}); },
      duerme: (ms) => new Promise((listo) => setTimeout(listo, ms)),

      // Repite funcion() hasta que regrese algo; anota la última respuesta.
      async hasta(funcion, {cada = 1000, limite = 60000, falla}) {
        const fin = Date.now() + limite;
        for (;;) {
          const valor = await funcion();
          if (valor) {
            if (h.ultima) anota({peticion: h.ultima});
            return valor;
          }
          if (Date.now() > fin) throw new Error(falla);
          await h.duerme(cada);
        }
      },

      async iniciaSesion(cuenta, usuario, password, captchaId, captchaRespuesta) {
        const r = await h.pide("auth", "POST", "/api/v1/auth/login",
          {json: {usuario, password, captcha_id: captchaId, captcha_respuesta: captchaRespuesta}});
        h.estado(r, 200);
        sesiones[cuenta] = {access: r.datos.access_token, refresh: r.datos.refresh_token, usuario: r.datos.usuario};
        h.espera(Boolean(r.datos.access_token && r.datos.refresh_token), "recibió el access y el refresh");
        h.espera(r.datos.usuario.roles.includes(CUENTAS[cuenta].rol), `${usuario} tiene el rol ${CUENTAS[cuenta].rol}`);
      },

      renueva(cuenta, datos) {
        sesiones[cuenta] = {...sesiones[cuenta], access: datos.access_token, refresh: datos.refresh_token};
      },
    };
    return h;
  }

  async function lanzaCorrida(h, semilla, clave) {
    const alta = await h.pide("corridas", "POST", "/api/v1/runs",
      {cuenta: "analista", json: {scenario_version_id: h.ctx.version_id, seed: semilla}});
    h.estado(alta, 202);
    const id = h.guarda(clave, alta.datos.id);
    const final = await h.hasta(async () => {
      const r = await h.pide("corridas", "GET", `/api/v1/runs/${id}`, {cuenta: "analista", silencioso: true});
      h.estado(r, 200);
      h.progreso(`Corrida ${id}: ${r.datos.status}` + (r.datos.progress === null ? "" : `, ${r.datos.progress} %`));
      return TERMINADAS.includes(r.datos.status) && r.datos;
    }, {cada: 1000, limite: 180000, falla: `La corrida ${id} no terminó en 3 minutos.`});
    h.espera(final.status === "completado", `la corrida ${id} llegó a completado`,
      `La corrida ${id} terminó en ${final.status}: ${final.error_message || "sin mensaje"}.`);
  }

  async function saludDeTodos(h, condicion, falla, limite) {
    return h.hasta(async () => {
      const r = await h.pide("estado-servicios", "GET", "/api/v1/services/health", {silencioso: true});
      h.estado(r, 200);
      h.progreso(`Salud: ${r.datos.resumen.ok} ok, ${r.datos.resumen.degradado} degradados y ` +
        `${r.datos.resumen.caido} caídos`);
      return condicion(r.datos) && r.datos;
    }, {cada: 3000, limite, falla});
  }

  const PASOS = [
    {n: "1", titulo: "Levantar todo desde cero",
     manual: "En la raíz del repositorio, crea infra/.env y levanta todo. En docker compose ps, " +
       "todos los servicios, la consola, PostgreSQL y Redis deben quedar healthy.",
     comandos: ["python infra/genera_env.py", `${COMPOSE} --profile '*' up -d --build --wait`, `${COMPOSE} ps`]},

    {n: "2", titulo: "El panel de salud muestra todos en verde", async correr(h) {
      const r = await h.pide("estado-servicios", "GET", "/api/v1/services/health");
      h.estado(r, 200);
      const fuera = r.datos.servicios.filter((s) => s.estado !== "ok").map((s) => s.nombre);
      h.espera(r.datos.servicios.length > 0 && !fuera.length, `los ${r.datos.servicios.length} están en ok`,
        `No están en ok: ${fuera.join(", ")}.`);
    }},

    {n: "3", titulo: "/health de un servicio en XML, en JSON con ?format=json y con Accept", async correr(h) {
      const xml = await h.pide("regiones", "GET", "/health", {formato: null});
      h.estado(xml, 200);
      h.espera(xml.tipo.startsWith("application/xml"), "sin parámetro responde XML");
      const json = await h.pide("regiones", "GET", "/health");
      h.estado(json, 200);
      h.espera(json.tipo.startsWith("application/json"), "con ?format=json responde JSON");
      const accept = await h.pide("regiones", "GET", "/health", {formato: null, accept: "application/json"});
      h.estado(accept, 200);
      h.espera(accept.tipo.startsWith("application/json"), "con Accept: application/json responde JSON");
    }},

    {n: "4", titulo: "Abrir el Swagger de varios servicios desde el selector",
     manual: "En la pestaña Swagger, abre el de auth, escenarios y resultados. Con una sesión " +
       "iniciada arriba, un Try it out lleva el token."},

    {n: "5", titulo: "Iniciar sesión como analista: recibir access y refresh", sesion: "analista"},

    {n: "6", titulo: "Consultar el catálogo de enfermedades en XML y en JSON", async correr(h) {
      const xml = await h.pide("enfermedades", "GET", "/api/v1/diseases", {formato: null});
      h.estado(xml, 200);
      h.espera(xml.tipo.startsWith("application/xml"), "el catálogo en XML");
      const json = await h.pide("enfermedades", "GET", "/api/v1/diseases");
      h.estado(json, 200);
      h.espera(json.tipo.startsWith("application/json"), "el catálogo en JSON");
      const enfermedades = json.datos.enfermedades;
      const elegida = enfermedades.find((e) => e.code === "INFLUENZA_ESTACIONAL") ||
        enfermedades.find((e) => e.activa && e.parametros && e.parametros.simulable);
      h.espera(Boolean(elegida), "hay una enfermedad simulable para el escenario del paso 8");
      h.guarda("disease_id", elegida.id);
    }},

    {n: "7a", titulo: "Iniciar sesión como administrador (los casos los captura CAPTURISTA o ADMINISTRADOR)",
     sesion: "admin"},

    {n: "7b", titulo: "Registrar un caso, y un lote de sincronización enviado dos veces sin duplicar",
     async correr(h) {
       h.necesita("disease_id");
       const regiones = await h.pide("regiones", "GET", "/api/v1/regions");
       h.estado(regiones, 200);
       const municipio = regiones.datos.municipios.find((m) => m.code === "19039") || regiones.datos.municipios[0];
       h.guarda("region_id", municipio.id);
       h.ctx.poblacion = municipio.poblacion;
       const caso = (localUuid) => ({local_uuid: localUuid, disease_id: h.ctx.disease_id,
                                     region_id: municipio.id, report_date: hoy(), test_result: "positivo"});
       const alta = await h.pide("casos", "POST", "/api/v1/cases", {cuenta: "admin", json: caso(nuevoId())});
       h.estado(alta, 201);
       h.guarda("case_id", alta.datos.id);
       const lote = {batch_id: nuevoId(), cases: [caso(nuevoId()), caso(nuevoId())]};
       const primero = await h.pide("sincronizacion", "POST", "/api/v1/sync/cases", {cuenta: "admin", json: lote});
       h.estado(primero, 200);
       h.espera(primero.datos.creados === 2, "el lote creó sus 2 casos");
       h.guarda("batch_id", lote.batch_id);
       const segundo = await h.pide("sincronizacion", "POST", "/api/v1/sync/cases", {cuenta: "admin", json: lote});
       h.estado(segundo, 200);
       const ids = (r) => r.datos.resultados.map((x) => x.case_id).join(",");
       h.espera(segundo.datos.repetido === true && ids(segundo) === ids(primero),
         "el mismo lote, enviado otra vez, regresa los mismos casos sin crear otros");
     }},

    {n: "8", titulo: "Crear un escenario en JSON y agregarle intervenciones", async correr(h) {
      h.necesita("disease_id", "region_id");
      const alta = await h.pide("escenarios", "POST", "/api/v1/scenarios", {cuenta: "analista", json: {
        name: "Recorrido de aceptación " + new Date().toLocaleString("es-MX"),
        description: "Creado por el recorrido de aceptación de la consola.",
        disease_id: h.ctx.disease_id, region_id: h.ctx.region_id, population_size: h.ctx.poblacion,
        horizon_days: 90, initial_infected: 10, stratify: false, notes: null}});
      h.estado(alta, 201);
      const escenario = h.guarda("scenario_id", alta.datos.id);
      const detalle = await h.pide("escenarios", "GET", `/api/v1/scenarios/${escenario}`, {cuenta: "analista"});
      h.estado(detalle, 200);
      const version = h.guarda("version_id", detalle.datos.version.id);
      const intervenciones = [
        {code: "VACUNACION", start_day: 10, end_day: null, coverage: 0.5, compliance: null,
         params: {eficacia: 0.7, dosis_diarias: 2000}},
        {code: "CIERRE_ESCUELAS", start_day: 15, end_day: 45, coverage: 1, compliance: 0.8, params: {}},
      ];
      const porTipo = {};
      for (const intervencion of intervenciones) {
        const r = await h.pide("intervenciones", "POST", `/api/v1/versions/${version}/interventions`,
          {cuenta: "analista", json: intervencion});
        h.estado(r, 201);
        porTipo[intervencion.code] = r.datos.id;
      }
      h.ctx.intervenciones_por_tipo = porTipo;
      h.guarda("intervenciones", Object.values(porTipo).join(", "));
    }},

    {n: "8b", titulo: "Capturar el costo de sus intervenciones, como supuesto",
     detalle: "pareto no traza la frontera sin el costo de cada intervención (regla 8), y en la " +
       "demostración ningún tipo lo tiene. El administrador del paso 7a lo fija con la marca de " +
       "supuesto. El costo vive en el tipo: cambia el de todos los escenarios de esta base.",
     entradas: [
       {clave: "VACUNACION", etiqueta: "Costo por dosis de VACUNACION, en pesos"},
       {clave: "CIERRE_ESCUELAS", etiqueta: "Costo por habitante y día de CIERRE_ESCUELAS, en pesos"},
     ],
     async correr(h, valores = {}) {
       h.necesita("version_id", "intervenciones_por_tipo");
       for (const [tipo, intervencion] of Object.entries(h.ctx.intervenciones_por_tipo)) {
         const importe = String(valores[tipo] === undefined ? "" : valores[tipo]).trim();
         if (!importe) throw new Error(`Escribe el costo de ${tipo}.`);
         const r = await h.pide("intervenciones", "PUT",
           `/api/v1/versions/${h.ctx.version_id}/interventions/${intervencion}/cost`,
           {cuenta: "admin", json: {unit_cost: importe, cost_source: FUENTE_SUPUESTO, cost_is_assumption: true}});
         h.estado(r, 200);
         h.espera(true, `${tipo}: ${importe} pesos, marcado como supuesto`);
       }
     }},

    {n: "9", titulo: "Exportarlo en XML y validarlo contra su XSD", async correr(h) {
      h.necesita("scenario_id");
      const xml = await h.pide("escenarios-xml", "GET", `/api/v1/scenarios/${h.ctx.scenario_id}/export`,
        {cuenta: "analista", formato: null});
      h.estado(xml, 200);
      h.espera(xml.tipo.startsWith("application/xml"), "el escenario completo, en XML");
      h.ctx.xml_exportado = xml.texto;
      const xsd = await h.pide("escenarios-xml", "GET", "/api/v1/schemas/scenario.xsd", {formato: null});
      h.estado(xsd, 200);
      h.nota("escenarios-xml valida contra este XSD cada XML que importa: el paso 10 importa este mismo.");
    }},

    {n: "10", titulo: "Importar un XML válido (crea el escenario) y uno inválido (422 con el detalle)",
     async correr(h) {
       h.necesita("xml_exportado");
       // El nombre es único por autor: el importado lleva otro.
       const copia = h.ctx.xml_exportado.replace(/<nombre>([^<]*)<\/nombre>/, "<nombre>$1 (importado)</nombre>");
       const valido = await h.pide("escenarios-xml", "POST", "/api/v1/scenarios/import",
         {cuenta: "analista", xml: copia});
       h.estado(valido, 201);
       h.espera(true, "el XML exportado pasa el XSD y crea otro escenario");
       h.guarda("scenario_id_importado", valido.datos.scenario_id);
       // Un elemento que el XSD no conoce, justo después de abrir la raíz.
       const roto = copia.replace(/(<[A-Za-z_][\w.-]*(?:\s[^>]*)?>)/, "$1<campo_que_no_existe>1</campo_que_no_existe>");
       const invalido = await h.pide("escenarios-xml", "POST", "/api/v1/scenarios/import",
         {cuenta: "analista", xml: roto});
       h.estado(invalido, 422);
       const errores = (invalido.datos && invalido.datos.errores) || [];
       h.espera(errores.length > 0, `el XML inválido regresa 422 con ${errores.length} error(es) de validación`);
     }},

    {n: "11", titulo: "Enviar a revisión e intentar aprobarlo como el mismo analista: rechazado",
     async correr(h) {
       h.necesita("scenario_id");
       const envio = await h.pide("aprobacion", "POST", `/api/v1/scenarios/${h.ctx.scenario_id}/submit`,
         {cuenta: "analista"});
       h.estado(envio, 200);
       h.espera(envio.datos.status === "en_revision", "la versión quedó en revisión");
       const propia = await h.pide("aprobacion", "POST", `/api/v1/scenarios/${h.ctx.scenario_id}/review`,
         {cuenta: "analista", json: {decision: "aprobar", comentario: "La analista intenta aprobar la suya."}});
       h.estado(propia, 403, 409);
       h.espera(true, `rechazado con ${propia.estado}: la analista no puede aprobar su propia versión`);
     }},

    {n: "12a", titulo: "Iniciar sesión como epidemióloga", sesion: "epidemiologo"},

    {n: "12b", titulo: "La epidemióloga lo aprueba; aparece la notificación", async correr(h) {
      h.necesita("scenario_id");
      const escenario = h.ctx.scenario_id;
      const r = await h.pide("aprobacion", "POST", `/api/v1/scenarios/${escenario}/review`,
        {cuenta: "epidemiologo", json: {decision: "aprobar", comentario: "Aprobado en el recorrido de aceptación."}});
      h.estado(r, 200);
      h.espera(r.datos.status === "aprobado", "la versión quedó aprobada");
      const aviso = await h.hasta(async () => {
        const lista = await h.pide("notificaciones", "GET", "/api/v1/notifications", {cuenta: "analista", silencioso: true});
        h.estado(lista, 200);
        return lista.datos.notificaciones.find((n) => n.type === "SCENARIO_APPROVED" &&
          n.payload && Number(n.payload.scenario_id) === escenario);
      }, {cada: 1000, limite: 10000, falla: "No llegó la notificación SCENARIO_APPROVED a la analista."});
      h.espera(true, "la analista recibió el aviso de aprobación");
      h.guarda("notificacion_id", aviso.id);
    }},

    {n: "13", titulo: "Lanzar una simulación y seguir su progreso hasta COMPLETADA", async correr(h) {
      h.necesita("version_id");
      await lanzaCorrida(h, 2026, "run_a");
    }},

    {n: "14", titulo: "Consultar resultados, comparar dos corridas y ver la frontera de Pareto",
     async correr(h) {
       h.necesita("run_a");
       h.nota("Para comparar hace falta otra corrida: la misma versión con otra semilla.");
       await lanzaCorrida(h, 2027, "run_b");
       const corridas = `${h.ctx.run_a},${h.ctx.run_b}`;
       const resultado = await h.pide("resultados", "GET", `/api/v1/runs/${h.ctx.run_a}/results`, {cuenta: "analista"});
       h.estado(resultado, 200);
       h.espera(Boolean(resultado.datos.aviso), "el resultado trae el aviso de que no es una predicción");
       const comparacion = await h.pide("comparacion", "GET", "/api/v1/comparisons",
         {cuenta: "analista", consulta: {runs: corridas}});
       h.estado(comparacion, 200);
       h.espera(comparacion.datos.corridas.length === 2, "compara las dos corridas lado a lado");
       const pareto = await h.pide("pareto", "GET", "/api/v1/pareto", {cuenta: "analista", consulta: {runs: corridas}});
       h.estado(pareto, 200);
       h.espera(Array.isArray(pareto.datos.frontera) && pareto.datos.frontera.length > 0,
         `la frontera de Pareto: ${(pareto.datos.frontera || []).join(", ")}`);
     }},

    {n: "15", titulo: "Renovar el token; reusar el refresh viejo cierra la sesión", async correr(h) {
      const viejo = h.sesion("analista").refresh;
      const renovado = await h.pide("sesiones", "POST", "/api/v1/sessions/refresh", {json: {refresh_token: viejo}});
      h.estado(renovado, 200);
      h.renueva("analista", renovado.datos);
      h.espera(true, "renovó: un access y un refresh nuevos");
      const reuso = await h.pide("sesiones", "POST", "/api/v1/sessions/refresh", {json: {refresh_token: viejo}});
      h.estado(reuso, 401);
      h.espera(true, "reusar el refresh viejo se rechaza");
      const actual = await h.pide("sesiones", "GET", "/api/v1/sessions/current", {cuenta: "analista"});
      h.estado(actual, 401);
      h.espera(true, "y cerró la sesión completa: ni el access nuevo sirve");
      h.olvida("analista");
    }},

    {n: "16", titulo: "Logout: el mismo token es rechazado por otro servicio (TOKEN_REVOCADO)",
     async correr(h) {
       const antes = await h.pide("aprobacion", "GET", "/api/v1/reviews/pending", {cuenta: "epidemiologo"});
       h.estado(antes, 200);
       const salida = await h.pide("sesiones", "POST", "/api/v1/sessions/logout", {cuenta: "epidemiologo"});
       h.estado(salida, 200);
       const despues = await h.pide("aprobacion", "GET", "/api/v1/reviews/pending", {cuenta: "epidemiologo"});
       h.estado(despues, 401);
       h.espera(despues.datos && despues.datos.codigo === "TOKEN_REVOCADO",
         "aprobacion rechaza el token con TOKEN_REVOCADO");
       h.olvida("epidemiologo");
     }},

    {n: "17", titulo: "Detener el contenedor de un servicio: aparece en rojo y los demás siguen",
     manual: "Detén un servicio y pulsa Comprobar: espera hasta el siguiente sondeo. Al terminar, " +
       "vuelve a levantarlo.",
     comandos: [`${COMPOSE} stop zonas`, `${COMPOSE} start zonas`],
     async comprobar(h) {
       const datos = await saludDeTodos(h, (d) => d.resumen.caido + d.resumen.degradado > 0, "Ningún servicio " +
         "salió del verde en 40 s: ¿lo detuviste?", 40000);
       const fuera = datos.servicios.filter((s) => s.estado !== "ok");
       h.espera(fuera.length === 1, `solo ${fuera[0].nombre} aparece en rojo (${fuera[0].causas.join(", ")})`,
         `Hay ${fuera.length} fuera de ok: ${fuera.map((s) => s.nombre).join(", ")}.`);
       h.espera(datos.resumen.ok === 25, "los otros 25 siguen en ok");
     }},

    {n: "18", titulo: "Detener Redis: lo protegido responde 503 y los catálogos siguen",
     manual: "Detén Redis y pulsa Comprobar. Usa la sesión del administrador del paso 7a.",
     comandos: [`${COMPOSE} stop redis`],
     async comprobar(h) {
       const protegida = await h.pide("casos", "GET", "/api/v1/cases", {cuenta: "admin"});
       h.estado(protegida, 503);
       h.espera(true, "una ruta protegida (casos) responde 503");
       const catalogo = await h.pide("regiones", "GET", "/api/v1/regions");
       h.estado(catalogo, 200);
       h.espera(true, "el catálogo de regiones sigue respondiendo");
     }},

    {n: "19", titulo: "Encender Redis: todo vuelve sin reiniciar servicios",
     manual: "Enciende Redis y pulsa Comprobar. No reinicies ningún servicio.",
     comandos: [`${COMPOSE} start redis`],
     async comprobar(h) {
       await h.hasta(async () => {
         const r = await h.pide("casos", "GET", "/api/v1/cases", {cuenta: "admin", silencioso: true});
         h.progreso(`casos responde ${r.estado}`);
         return r.estado === 200;
       }, {cada: 2000, limite: 60000, falla: "casos no volvió a responder 200 en un minuto."});
       h.espera(true, "lo protegido vuelve, con la misma sesión");
       await saludDeTodos(h, (d) => d.resumen.ok === d.servicios.length,
         "No volvieron todos a ok en un minuto.", 60000);
       h.espera(true, "todos vuelven a ok en el panel");
     }},

    {n: "20", titulo: "En el monolito: todo sigue funcionando contra la misma base",
     manual: "Apunta el monolito al PostgreSQL del compose (127.0.0.1:5433, ver docs/INSTALACION.md), " +
       "inicia sesión y revisa que el escenario y las corridas de este recorrido aparecen.",
     comandos: ["python -m frontend_web.run"]},

    {n: "21", titulo: "Consultar la bitácora: aparecen las operaciones hechas por la API, con usuario e IP",
     manual: "En el monolito, como administrador, abre la bitácora: deben aparecer el alta del escenario, " +
       "las intervenciones, la aprobación y las corridas de este recorrido, con su usuario y su IP."},

    {n: "22", titulo: "Correr las pruebas unitarias, las de contrato y las de integración",
     manual: "En la raíz del repositorio, con la base de pruebas al día.",
     comandos: ["python datos/scripts/prepara_base_pruebas.py", "python -m pytest"]},
  ];

  globalThis.Recorrido = {PASOS, CUENTAS, herramientas};
})();
