"use strict";

// La consola habla con cada servicio desde el navegador, con la URL que da el directorio de
// estado-servicios. El token vive solo en `estado`, en la memoria de la página: nunca se
// guarda en el navegador.
(() => {
  const SWAGGER = "https://unpkg.com/swagger-ui-dist@5.17.14";
  const CADA_SALUD = 10000;
  const TOKENES = /^(access_token|refresh_token|token)$/;
  const CLAVES = /password|contrase/i;

  const estado = {directorio: "", servicios: [], contratos: {}, sesion: null, captcha: null,
                  relojSalud: null, vista: "salud", operaciones: null};
  const $ = (id) => document.getElementById(id);

  // ----------------------------------------------------------------- utilidades

  function el(etiqueta, propiedades = {}, ...hijos) {
    const nodo = document.createElement(etiqueta);
    for (const [clave, valor] of Object.entries(propiedades)) {
      if (clave === "class") nodo.className = valor;
      else if (clave === "text") nodo.textContent = valor;
      else nodo.setAttribute(clave, valor);
    }
    nodo.append(...hijos);
    return nodo;
  }

  const recorta = (token) => (typeof token === "string" ? token.slice(0, 10) + "…" : token);
  const hora = (fecha) => fecha.toLocaleTimeString("es-MX", {hour: "2-digit", minute: "2-digit", second: "2-digit"});

  // Lo que se muestra no lleva contraseñas, y los tokens van recortados. Para un curl, en
  // cambio, se dejan marcas que se reemplazan a mano.
  const EN_PANTALLA = {password: () => "••••••", token: recorta};
  const EN_CURL = {password: () => "<contraseña>", token: () => "<token>"};

  function oculta(valor, reemplazo, clave = "") {
    if (Array.isArray(valor)) return valor.map((v) => oculta(v, reemplazo));
    if (valor && typeof valor === "object") {
      return Object.fromEntries(Object.entries(valor).map(([k, v]) => [k, oculta(v, reemplazo, k)]));
    }
    if (typeof valor === "string" && CLAVES.test(clave)) return reemplazo.password(valor);
    if (typeof valor === "string" && TOKENES.test(clave)) return reemplazo.token(valor);
    return valor;
  }

  function ocultaXML(documento, reemplazo) {
    for (const nodo of documento.getElementsByTagName("*")) {
      if (nodo.children.length) continue;
      if (CLAVES.test(nodo.localName)) nodo.textContent = reemplazo.password(nodo.textContent);
      else if (TOKENES.test(nodo.localName)) nodo.textContent = reemplazo.token(nodo.textContent);
    }
    return documento;
  }

  const escapa = (texto) => texto.replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  function xmlConSangria(documento) {
    const lineas = [];
    (function recorre(nodo, sangria) {
      const atributos = [...nodo.attributes].map((a) => ` ${a.name}="${escapa(a.value)}"`).join("");
      const hijos = [...nodo.children];
      if (!hijos.length) {
        const texto = nodo.textContent;
        lineas.push(texto ? `${sangria}<${nodo.nodeName}${atributos}>${escapa(texto)}</${nodo.nodeName}>`
          : `${sangria}<${nodo.nodeName}${atributos}/>`);
        return;
      }
      lineas.push(`${sangria}<${nodo.nodeName}${atributos}>`);
      hijos.forEach((hijo) => recorre(hijo, sangria + "  "));
      lineas.push(`${sangria}</${nodo.nodeName}>`);
    })(documento.documentElement, "");
    return lineas.join("\n");
  }

  const leeXML = (texto) => {
    const documento = new DOMParser().parseFromString(texto, "application/xml");
    return documento.getElementsByTagName("parsererror").length ? null : documento;
  };

  // El cuerpo de una respuesta, con formato y sin secretos.
  function legible(texto, tipo) {
    if (/json/.test(tipo || "")) {
      try { return JSON.stringify(oculta(JSON.parse(texto), EN_PANTALLA), null, 2); } catch (e) { return texto; }
    }
    if (/xml/.test(tipo || "")) {
      const documento = leeXML(texto);
      return documento ? xmlConSangria(ocultaXML(documento, EN_PANTALLA)) : texto;
    }
    return texto;
  }

  function mensajeDe(error) {
    if (error.name === "AbortError") return "no respondió a tiempo";
    if (error instanceof TypeError) {
      return "no respondió o bloqueó la petición (abre la consola en el origen de CONSOLE_ORIGIN, " +
        "por omisión http://localhost:5260)";
    }
    return error.message;
  }

  async function pide(url, opciones = {}, espera = 20000) {
    const control = new AbortController();
    const reloj = setTimeout(() => control.abort(), espera);
    const inicio = performance.now();
    try {
      const respuesta = await fetch(url, {...opciones, signal: control.signal});
      const texto = await respuesta.text();
      return {respuesta, texto, ms: Math.round(performance.now() - inicio)};
    } finally {
      clearTimeout(reloj);
    }
  }

  // Pide JSON; un error del servicio (RFC 7807) se lanza con su detail.
  async function pideJSON(url, opciones = {}) {
    const {respuesta, texto} = await pide(url, opciones);
    let datos = null;
    try { datos = JSON.parse(texto); } catch (e) { /* no era JSON */ }
    if (!respuesta.ok) throw new Error((datos && datos.detail) || `HTTP ${respuesta.status}`);
    return datos;
  }

  const servicio = (nombre) => estado.servicios.find((s) => s.nombre === nombre);
  const conToken = () => (estado.sesion ? {Authorization: "Bearer " + estado.sesion.access} : {});

  function avisa(id, texto, esError = false) {
    $(id).textContent = texto;
    $(id).classList.toggle("error", esError);
  }

  // ----------------------------------------------------------------- directorio y salud

  async function conectar() {
    estado.directorio = $("directorio").value.replace(/\/+$/, "");
    avisa("salud-hora", "Pidiendo el directorio…");
    try {
      estado.servicios = (await pideJSON(estado.directorio + "/api/v1/services?format=json")).servicios;
    } catch (error) {
      estado.servicios = [];
      avisa("salud-hora", "estado-servicios " + mensajeDe(error), true);
      return;
    }
    estado.contratos = {};
    for (const id of ["swagger-servicio", "probador-servicio"]) {
      $(id).replaceChildren(...estado.servicios.map((s) => el("option", {value: s.nombre, text: s.nombre})));
    }
    actualizaSalud();
    if (!estado.sesion) otroCaptcha();
    if (estado.vista === "swagger") muestraSwagger();
    if (estado.vista === "probador") eligeServicio();
  }

  const ESTADOS = {ok: "OK", degradado: "Degradado", caido: "Caído"};
  const CAUSAS = {postgresql: "PostgreSQL", redis: "Redis", proceso: "Proceso"};
  const DETALLES = {sin_conexion: "sin conexión", tiempo_agotado: "tiempo agotado",
                    respuesta_invalida: "respuesta inválida"};

  function pintaSalud(datos) {
    $("salud-resumen").replaceChildren(...Object.entries(ESTADOS).map(([clave, nombre]) =>
      el("span", {class: "insignia " + clave, text: `${nombre}: ${datos.resumen[clave]}`})));
    $("salud-filas").replaceChildren(...datos.servicios.map((s) => {
      const directorio = servicio(s.nombre) || {};
      const causa = s.causas.map((c) => CAUSAS[c] || c).join(", ") +
        (s.detalle ? ` (${DETALLES[s.detalle] || s.detalle})` : "");
      return el("tr", {class: s.estado},
        el("td", {}, directorio.docs
          ? el("a", {href: directorio.docs, target: "_blank", rel: "noopener", text: s.nombre}) : s.nombre),
        el("td", {text: directorio.dominio || ""}),
        el("td", {}, el("span", {class: "insignia " + s.estado, text: ESTADOS[s.estado] || s.estado})),
        el("td", {text: causa || "—"}),
        el("td", {text: s.version || "—"}),
        el("td", {class: "numero", text: s.latencia_ms === null ? "—" : `${s.latencia_ms} ms`}),
        el("td", {text: hora(new Date(s.revisado))}));
    }));
  }

  async function actualizaSalud() {
    clearTimeout(estado.relojSalud);
    try {
      pintaSalud(await pideJSON(estado.directorio + "/api/v1/services/health?format=json"));
      avisa("salud-hora", `Actualizado a las ${hora(new Date())}; se actualiza cada ${CADA_SALUD / 1000} s.`);
    } catch (error) {
      avisa("salud-hora", "estado-servicios " + mensajeDe(error), true);
    }
    estado.relojSalud = setTimeout(actualizaSalud, CADA_SALUD);
  }

  // ----------------------------------------------------------------- sesión

  async function otroCaptcha() {
    if (!servicio("auth")) return;
    try {
      const datos = await pideJSON(servicio("auth").url + "/api/v1/auth/captcha?format=json");
      estado.captcha = datos.captcha_id;
      $("captcha-pregunta").textContent = `¿Cuánto es ${datos.pregunta}?`;
      $("login-captcha").value = "";
    } catch (error) {
      avisa("sesion-mensaje", "auth " + mensajeDe(error), true);
    }
  }

  function pintaSesion() {
    const activa = Boolean(estado.sesion);
    $("form-login").hidden = activa;
    $("sesion-activa").hidden = !activa;
    if (!activa) return;
    const {usuario, access, vence} = estado.sesion;
    $("sesion-datos").textContent = `${usuario.username} (${usuario.roles.join(", ")}) · token ` +
      `${recorta(access)} · vence a las ${hora(vence)}`;
  }

  function guardaSesion(datos, usuario) {
    estado.sesion = {access: datos.access_token, refresh: datos.refresh_token, usuario,
                     vence: new Date(Date.now() + datos.expires_in * 1000)};
    pintaSesion();
  }

  async function iniciaSesion(evento) {
    evento.preventDefault();
    const contrasena = $("login-password");
    const cuerpo = {usuario: $("login-usuario").value, password: contrasena.value,
                    captcha_id: estado.captcha, captcha_respuesta: $("login-captcha").value};
    contrasena.value = "";
    try {
      const datos = await pideJSON(servicio("auth").url + "/api/v1/auth/login?format=json", {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(cuerpo)});
      guardaSesion(datos, datos.usuario);
      avisa("sesion-mensaje", "Sesión iniciada.");
    } catch (error) {
      avisa("sesion-mensaje", error.message, true);
      otroCaptcha();
    }
  }

  async function renueva() {
    try {
      const datos = await pideJSON(servicio("sesiones").url + "/api/v1/sessions/refresh?format=json", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({refresh_token: estado.sesion.refresh})});
      guardaSesion(datos, estado.sesion.usuario);
      avisa("sesion-mensaje", "Token renovado; el refresh anterior ya no sirve.");
    } catch (error) {
      avisa("sesion-mensaje", error.message, true);
    }
  }

  async function cierraSesion() {
    try {
      await pideJSON(servicio("sesiones").url + "/api/v1/sessions/logout?format=json",
                     {method: "POST", headers: conToken()});
      avisa("sesion-mensaje", "Sesión cerrada en sesiones.");
    } catch (error) {
      avisa("sesion-mensaje", `La sesión se olvidó aquí, pero sesiones respondió: ${error.message}`, true);
    }
    estado.sesion = null;
    pintaSesion();
    otroCaptcha();
  }

  // ----------------------------------------------------------------- contratos y Swagger

  async function contrato(nombre) {
    if (!estado.contratos[nombre]) {
      estado.contratos[nombre] = await pideJSON(servicio(nombre).openapi);
    }
    return estado.contratos[nombre];
  }

  let swaggerListo = null;
  function cargaSwagger() {
    swaggerListo = swaggerListo || new Promise((listo, falla) => {
      document.head.append(el("link", {rel: "stylesheet", href: SWAGGER + "/swagger-ui.css"}));
      const script = el("script", {src: SWAGGER + "/swagger-ui-bundle.js"});
      script.onload = listo;
      script.onerror = () => { swaggerListo = null; falla(new Error("No se pudo cargar Swagger UI de unpkg.com.")); };
      document.head.append(script);
    });
    return swaggerListo;
  }

  // Lo que regresa "Try it out", sin secretos, igual que en el probador.
  function limpiaRespuesta(respuesta) {
    if (typeof respuesta.text === "string") {
      const tipo = (respuesta.headers && respuesta.headers["content-type"]) || "";
      const texto = legible(respuesta.text, tipo);
      respuesta.text = respuesta.data = texto;
      if (/json/.test(tipo)) {
        try { respuesta.body = respuesta.obj = JSON.parse(texto); } catch (e) { /* se queda el texto */ }
      }
    }
    return respuesta;
  }

  async function muestraSwagger() {
    const nombre = $("swagger-servicio").value;
    if (!nombre) return;
    avisa("swagger-mensaje", "Cargando el contrato de " + nombre + "…");
    try {
      await cargaSwagger();
      const especificacion = structuredClone(await contrato(nombre));
      // "Try it out" va a la URL del directorio, no a la que trae escrita el contrato.
      especificacion.servers = [{url: servicio(nombre).url}];
      window.SwaggerUIBundle({
        spec: especificacion, dom_id: "#swagger", deepLinking: false,
        requestInterceptor: (peticion) => {
          if (estado.sesion && !peticion.headers.Authorization) Object.assign(peticion.headers, conToken());
          return peticion;
        },
        responseInterceptor: limpiaRespuesta,
      });
      avisa("swagger-mensaje", "");
    } catch (error) {
      avisa("swagger-mensaje", nombre + ": " + mensajeDe(error), true);
    }
  }

  // ----------------------------------------------------------------- probador

  function operacionesDe(especificacion) {
    const operaciones = [];
    for (const [ruta, metodos] of Object.entries(especificacion.paths)) {
      for (const [metodo, operacion] of Object.entries(metodos)) {
        if (["get", "post", "put", "patch", "delete"].includes(metodo)) {
          operaciones.push({ruta, metodo: metodo.toUpperCase(), operacion});
        }
      }
    }
    return operaciones;
  }

  function ejemploDe(operacion, formato) {
    const contenido = ((operacion.requestBody || {}).content || {})["application/" + formato];
    if (!contenido) return "";
    if (contenido.example !== undefined) {
      return typeof contenido.example === "string" ? contenido.example : JSON.stringify(contenido.example, null, 2);
    }
    const primero = Object.values(contenido.examples || {})[0];
    return primero ? primero.value : "";
  }

  async function eligeServicio() {
    const nombre = $("probador-servicio").value;
    if (!nombre) return;
    try {
      estado.operaciones = operacionesDe(await contrato(nombre));
    } catch (error) {
      estado.operaciones = [];
      $("probador-descripcion").textContent = nombre + ": " + mensajeDe(error);
    }
    $("probador-operacion").replaceChildren(...estado.operaciones.map((o, i) =>
      el("option", {value: String(i), text: `${o.metodo} ${o.ruta}`})));
    eligeOperacion();
  }

  function eligeOperacion() {
    const elegida = estado.operaciones[Number($("probador-operacion").value)];
    $("probador-resultado").hidden = $("probador-comando").hidden = true;
    if (!elegida) return;
    const {ruta, operacion} = elegida;
    $("probador-descripcion").textContent = operacion.summary || "";
    // Las rutas públicas no reciben el token.
    $("probador-token").checked = Boolean(operacion.security && operacion.security.length);
    const deRuta = [...ruta.matchAll(/\{([^}]+)\}/g)].map((m) => m[1]);
    const parametros = (operacion.parameters || []).filter((p) => p.in === "path" || p.in === "query");
    const campos = deRuta.map((n) => parametros.find((p) => p.name === n && p.in === "path") || {name: n, in: "path"})
      .concat(parametros.filter((p) => p.in === "query" && p.name !== "format"));
    $("probador-campos").replaceChildren(...campos.map((p) => {
      const ejemplo = p.example !== undefined ? p.example : (p.schema || {}).default;
      const entrada = el("input", {"data-nombre": p.name, "data-en": p.in, spellcheck: "false"});
      entrada.value = ejemplo === undefined ? "" : String(ejemplo);
      if (p.in === "path") entrada.required = true;
      return el("label", {}, `${p.name}${p.in === "path" ? " (ruta)" : ""}`, entrada);
    }));
    $("probador-parametros").hidden = !campos.length;
    const conCuerpo = Boolean(operacion.requestBody);
    $("probador-cuerpo").hidden = !conCuerpo;
    if (conCuerpo) {
      const formato = ejemploDe(operacion, "json") ? "json" : "xml";
      $("probador-formato-cuerpo").value = formato;
      $("probador-texto").value = ejemploDe(operacion, formato);
    }
  }

  function cambiaFormatoCuerpo() {
    const elegida = estado.operaciones[Number($("probador-operacion").value)];
    if (elegida) $("probador-texto").value = ejemploDe(elegida.operacion, $("probador-formato-cuerpo").value);
  }

  function armaPeticion() {
    const {ruta, metodo, operacion} = estado.operaciones[Number($("probador-operacion").value)];
    let camino = ruta;
    const consulta = new URLSearchParams();
    for (const entrada of $("probador-campos").querySelectorAll("input")) {
      if (entrada.dataset.en === "path") {
        camino = camino.replace(`{${entrada.dataset.nombre}}`, encodeURIComponent(entrada.value));
      } else if (entrada.value !== "") {
        consulta.set(entrada.dataset.nombre, entrada.value);
      }
    }
    const formato = $("probador-formato").value;
    const cabeceras = {};
    if (formato === "json") consulta.set("format", "json");
    if (formato === "accept") cabeceras.Accept = "application/json";
    if ($("probador-token").checked) Object.assign(cabeceras, conToken());
    const peticion = {method: metodo, headers: cabeceras};
    if (operacion.requestBody) {
      const tipo = $("probador-formato-cuerpo").value;
      cabeceras["Content-Type"] = "application/" + tipo;
      peticion.body = $("probador-texto").value;
    }
    const texto = consulta.toString();
    return {url: servicio($("probador-servicio").value).url + camino + (texto ? "?" + texto : ""), peticion};
  }

  const hayOperacion = () => Boolean(estado.operaciones && estado.operaciones.length);

  async function envia(evento) {
    evento.preventDefault();
    if (!hayOperacion()) return;
    const boton = evento.submitter || $("form-probador").querySelector("button[type=submit]");
    const {url, peticion} = armaPeticion();
    boton.disabled = true;
    $("probador-resultado").hidden = false;
    $("probador-estado").textContent = "Enviando…";
    $("probador-estado").className = "estado-http";
    $("probador-cabeceras").replaceChildren();
    $("probador-respuesta").textContent = "";
    try {
      const {respuesta, texto, ms} = await pide(url, peticion, 60000);
      $("probador-estado").textContent = `${respuesta.status} ${respuesta.statusText} · ${ms} ms`;
      $("probador-estado").classList.add(respuesta.ok ? "bien" : "mal");
      $("probador-cabeceras").replaceChildren(...[...respuesta.headers].flatMap(([nombre, valor]) =>
        [el("dt", {text: nombre}), el("dd", {text: valor})]));
      $("probador-respuesta").textContent = legible(texto, respuesta.headers.get("content-type")) || "(sin cuerpo)";
    } catch (error) {
      $("probador-estado").textContent = "Sin respuesta: el servicio " + mensajeDe(error);
      $("probador-estado").classList.add("mal");
    } finally {
      boton.disabled = false;
    }
  }

  // El cuerpo de un curl, sin la contraseña ni los tokens que lleve.
  function cuerpoParaCurl(texto, tipo) {
    if (tipo === "application/json") {
      try { return JSON.stringify(oculta(JSON.parse(texto), EN_CURL)); } catch (e) { return texto; }
    }
    const documento = leeXML(texto);
    return documento ? new XMLSerializer().serializeToString(ocultaXML(documento, EN_CURL)) : texto;
  }

  function comoCurl({url, peticion}) {
    const comillas = (texto) => "'" + String(texto).replace(/'/g, "'\\''") + "'";
    const partes = ["curl", "-X", peticion.method, comillas(url)];
    for (const [nombre, valor] of Object.entries(peticion.headers)) {
      partes.push("-H", nombre === "Authorization" ? '"Authorization: Bearer $TOKEN"' : comillas(`${nombre}: ${valor}`));
    }
    if (peticion.body) partes.push("--data-raw", comillas(cuerpoParaCurl(peticion.body, peticion.headers["Content-Type"])));
    return partes.join(" ");
  }

  async function copiaCurl() {
    if (!hayOperacion()) return;
    const comando = comoCurl(armaPeticion());
    $("probador-comando").textContent = comando;
    $("probador-comando").hidden = false;
    try {
      await navigator.clipboard.writeText(comando);
    } catch (error) {
      // Sin permiso para el portapapeles: el comando queda a la vista para copiarlo a mano.
    }
  }

  // ----------------------------------------------------------------- recorrido de aceptación

  // Los pasos están en recorrido.js. Aquí se pintan, se corren en orden y se anota lo que
  // regresa cada petición. Sus sesiones son aparte de la de arriba y tampoco se guardan.
  const recorrido = {pasos: [], sesiones: {}, guardados: {}, h: null, actual: null, ocupado: false};
  const ESTADOS_PASO = {pendiente: "Pendiente", corriendo: "Corriendo…", bien: "Bien", fallo: "Falló", hecho: "Hecho"};

  function nuevoRecorrido() {
    recorrido.sesiones = {};
    recorrido.guardados = {};
    recorrido.h = window.Recorrido.herramientas({
      urlDe: (nombre) => {
        if (!servicio(nombre)) throw new Error(`El directorio no tiene ${nombre}: conecta la consola con estado-servicios.`);
        return servicio(nombre).url;
      },
      pide, sesiones: recorrido.sesiones, anota: (evento) => anotaPaso(recorrido.actual, evento),
    });
    recorrido.pasos = window.Recorrido.PASOS.map((def) => ({def, estado: "pendiente", eventos: []}));
    $("recorrido-pasos").replaceChildren(...recorrido.pasos.map(tarjetaPaso));
    pintaGuardados();
    avisa("recorrido-mensaje", "");
  }

  function lineaDe(evento) {
    if (evento.peticion) {
      const r = evento.peticion;
      const linea = el("li", {class: "peticion " + (r.estado < 400 ? "bien" : "mal")},
        `${r.metodo} ${r.servicio} ${r.ruta} → ${r.estado} · ${r.ms} ms`);
      if (r.texto) {
        linea.append(el("details", {}, el("summary", {text: "Respuesta"}),
          el("pre", {class: "codigo", text: legible(r.texto, r.tipo)})));
      }
      return linea;
    }
    if (evento.bien) return el("li", {class: "bien", text: "✓ " + evento.bien});
    if (evento.falla) return el("li", {class: "falla", text: "✗ " + evento.falla});
    if (evento.guardado) return el("li", {class: "guardado", text: `${evento.guardado[0]} = ${evento.guardado[1]}`});
    return el("li", {class: "nota", text: evento.nota});
  }

  function anotaPaso(paso, evento) {
    if (!paso) return;
    if (evento.progreso) {
      if (!paso.lineaProgreso) {
        paso.lineaProgreso = el("li", {class: "nota"});
        paso.bitacora.append(paso.lineaProgreso);
      }
      paso.lineaProgreso.textContent = evento.progreso;
      return;
    }
    if (evento.guardado) recorrido.guardados[evento.guardado[0]] = evento.guardado[1];
    // El resumen descargable lleva cada petición sin su cuerpo.
    const {texto, datos, ...peticion} = evento.peticion || {};
    paso.eventos.push(evento.peticion ? {peticion} : evento);
    paso.bitacora.append(lineaDe(evento));
  }

  function pintaPaso(paso) {
    paso.insignia.className = "insignia " + paso.estado;
    paso.insignia.textContent = ESTADOS_PASO[paso.estado];
    paso.nodo.className = "paso " + paso.estado;
  }

  function pintaGuardados() {
    const valores = Object.entries(recorrido.guardados);
    $("recorrido-guardados").replaceChildren(...(valores.length
      ? valores.flatMap(([clave, valor]) => [el("dt", {text: clave}), el("dd", {text: String(valor)})])
      : [el("dd", {text: "Todavía nada."})]));
  }

  async function correPaso(paso, accion) {
    if (recorrido.ocupado) return false;
    recorrido.ocupado = true;
    recorrido.actual = paso;
    paso.estado = "corriendo";
    paso.eventos = [];
    paso.lineaProgreso = null;
    paso.bitacora.replaceChildren();
    pintaPaso(paso);
    try {
      await accion(recorrido.h);
      paso.estado = "bien";
    } catch (error) {
      anotaPaso(paso, {falla: mensajeDe(error)});
      paso.estado = "fallo";
    } finally {
      recorrido.ocupado = false;
    }
    pintaPaso(paso);
    pintaGuardados();
    return paso.estado === "bien";
  }

  async function captchaDePaso(paso) {
    try {
      const datos = await pideJSON(servicio("auth").url + "/api/v1/auth/captcha?format=json");
      paso.captcha.id = datos.captcha_id;
      paso.captcha.pregunta.textContent = `¿Cuánto es ${datos.pregunta}?`;
      paso.captcha.respuesta.value = "";
    } catch (error) {
      paso.captcha.pregunta.textContent = "auth " + mensajeDe(error);
    }
  }

  function formularioSesion(paso) {
    const cuenta = window.Recorrido.CUENTAS[paso.def.sesion];
    const usuario = el("input", {autocomplete: "username", spellcheck: "false", required: ""});
    usuario.value = cuenta.usuario;
    const clave = el("input", {type: "password", autocomplete: "current-password", required: ""});
    paso.captcha = {id: null, pregunta: el("span", {text: "Captcha"}),
                    respuesta: el("input", {inputmode: "numeric", autocomplete: "off", required: ""})};
    const otro = el("button", {type: "button", class: "secundario", text: "Otro captcha"});
    otro.addEventListener("click", () => captchaDePaso(paso));
    const formulario = el("form", {class: "login", method: "post"},
      el("label", {}, `Usuario (${cuenta.rol})`, usuario), el("label", {}, "Contraseña", clave),
      el("label", {}, paso.captcha.pregunta, paso.captcha.respuesta),
      el("div", {class: "acciones"}, otro, el("button", {type: "submit", text: "Iniciar sesión"})));
    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const contrasena = clave.value;
      clave.value = "";
      const listo = await correPaso(paso, (h) => h.iniciaSesion(paso.def.sesion, usuario.value, contrasena,
                                                              paso.captcha.id, paso.captcha.respuesta.value));
      // Cada captcha sirve una vez, salga bien o mal.
      paso.captcha.id = null;
      if (listo) sigue(); else captchaDePaso(paso);
    });
    return formulario;
  }

  function formularioEntradas(paso) {
    const campos = paso.def.entradas.map((entrada) =>
      [entrada.clave, el("input", {inputmode: "decimal", autocomplete: "off", required: ""}), entrada.etiqueta]);
    const formulario = el("form", {class: "rejilla", method: "post"},
      ...campos.map(([, entrada, etiqueta]) => el("label", {}, etiqueta, entrada)),
      el("div", {class: "acciones"}, el("button", {type: "submit", text: "Correr"})));
    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const valores = Object.fromEntries(campos.map(([clave, entrada]) => [clave, entrada.value]));
      if (await correPaso(paso, (h) => paso.def.correr(h, valores))) sigue();
    });
    return formulario;
  }

  function botonPaso(texto, accion, clase = "") {
    const boton = el("button", {type: "button", class: clase, text: texto});
    boton.addEventListener("click", accion);
    return boton;
  }

  function tarjetaPaso(paso) {
    const {def} = paso;
    paso.insignia = el("span");
    paso.bitacora = el("ul", {class: "bitacora"});
    const partes = [];
    if (def.detalle) partes.push(el("p", {class: "nota", text: def.detalle}));
    if (def.manual) partes.push(el("p", {text: def.manual}));
    if (def.comandos) partes.push(el("pre", {class: "codigo", text: def.comandos.join("\n")}));
    if (def.sesion) {
      partes.push(formularioSesion(paso));
    } else if (def.entradas) {
      partes.push(formularioEntradas(paso));
    } else if (def.manual && !def.comprobar) {
      partes.push(el("div", {class: "acciones"}, botonPaso("Listo", () => {
        paso.estado = "hecho";
        pintaPaso(paso);
        sigue();
      })));
    } else {
      const accion = def.comprobar || def.correr;
      partes.push(el("div", {class: "acciones"}, botonPaso(def.comprobar ? "Comprobar" : "Correr", async () => {
        if (await correPaso(paso, accion) && def.comprobar) sigue();
      }, "secundario")));
    }
    paso.nodo = el("li", {}, el("div", {class: "paso-cabeza"}, el("span", {class: "paso-numero", text: def.n}),
      el("h3", {text: def.titulo}), paso.insignia), ...partes, paso.bitacora);
    pintaPaso(paso);
    return paso.nodo;
  }

  function atiende(paso) {
    paso.nodo.scrollIntoView({behavior: "smooth", block: "center"});
    if (paso.def.sesion && !paso.captcha.id) captchaDePaso(paso);
    avisa("recorrido-mensaje", `El paso ${paso.def.n} lo completa la persona.`);
  }

  // Corre en orden, desde el primero que no ha salido bien, hasta uno que pida algo a la
  // persona (sesión, importes o algo que hacer fuera de la consola) o que falle.
  async function sigue() {
    for (const paso of recorrido.pasos) {
      if (paso.estado === "bien" || paso.estado === "hecho") continue;
      if (paso.def.sesion || paso.def.entradas || paso.def.manual) {
        atiende(paso);
        return;
      }
      if (!await correPaso(paso, paso.def.correr)) {
        paso.nodo.scrollIntoView({behavior: "smooth", block: "center"});
        avisa("recorrido-mensaje", `El paso ${paso.def.n} falló; corrígelo y vuelve a correrlo.`, true);
        return;
      }
    }
    avisa("recorrido-mensaje", "Recorrido completo. Descarga el resumen para las evidencias.");
  }

  function reinicia() {
    if (window.confirm("¿Empezar de nuevo? Se olvidan los ids y las sesiones del recorrido.")) nuevoRecorrido();
  }

  function descargaResumen() {
    const resumen = {recorrido: "Prueba de aceptación del segundo parcial", fecha: new Date().toISOString(),
                     directorio: estado.directorio, guardados: recorrido.guardados,
                     pasos: recorrido.pasos.map((p) => ({n: p.def.n, titulo: p.def.titulo, estado: p.estado,
                                                         eventos: p.eventos}))};
    const archivo = new Blob([JSON.stringify(resumen, null, 2)], {type: "application/json"});
    const enlace = el("a", {href: URL.createObjectURL(archivo),
                            download: `recorrido-aceptacion-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "")}.json`});
    document.body.append(enlace);
    enlace.click();
    enlace.remove();
    setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
  }

  // ----------------------------------------------------------------- pestañas y arranque

  const VISTAS = ["salud", "swagger", "probador", "recorrido"];

  function muestraVista(vista) {
    estado.vista = vista;
    for (const nombre of VISTAS) {
      $("vista-" + nombre).hidden = nombre !== vista;
      $("pestana-" + nombre).setAttribute("aria-selected", String(nombre === vista));
    }
    if (vista === "swagger") muestraSwagger();
    if (vista === "probador" && !estado.operaciones) eligeServicio();
  }

  document.addEventListener("DOMContentLoaded", async () => {
    for (const nombre of VISTAS) {
      $("pestana-" + nombre).addEventListener("click", () => muestraVista(nombre));
    }
    $("form-directorio").addEventListener("submit", (evento) => { evento.preventDefault(); conectar(); });
    $("form-login").addEventListener("submit", iniciaSesion);
    $("otro-captcha").addEventListener("click", otroCaptcha);
    $("renovar").addEventListener("click", renueva);
    $("cerrar").addEventListener("click", cierraSesion);
    $("swagger-servicio").addEventListener("change", muestraSwagger);
    $("probador-servicio").addEventListener("change", eligeServicio);
    $("probador-operacion").addEventListener("change", eligeOperacion);
    $("probador-formato-cuerpo").addEventListener("change", cambiaFormatoCuerpo);
    $("form-probador").addEventListener("submit", envia);
    $("probador-curl").addEventListener("click", copiaCurl);
    $("recorrido-sigue").addEventListener("click", sigue);
    $("recorrido-reinicia").addEventListener("click", reinicia);
    $("recorrido-descarga").addEventListener("click", descargaResumen);
    nuevoRecorrido();
    try {
      $("directorio").value = (await pideJSON("/config?format=json")).directorio;
    } catch (error) {
      $("directorio").value = "http://localhost:5262";
    }
    conectar();
  });
})();
