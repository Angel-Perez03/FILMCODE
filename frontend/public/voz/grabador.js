import { lecturas } from './lecturas.js';
import { crearWav } from './wav.js';

const elemento = (id) => document.getElementById(id);
const selector = elemento('lectura');
const grabar = elemento('grabar');
const parar = elemento('detener');
const estado = elemento('estado');
const error = elemento('error');
const reloj = elemento('tiempo');
const progreso = elemento('progreso');
const nivel = elemento('nivel');
const tomas = [];
let activa = null;
let secuencia = 0;
const MAX_TOMAS = 20;

for (const lectura of lecturas) {
  const opcion = document.createElement('option');
  opcion.value = lectura.id;
  opcion.textContent = lectura.titulo;
  selector.append(opcion);
}

function elegir() {
  const lectura = lecturas.find((item) => item.id === selector.value) || lecturas[0];
  elemento('texto').textContent = lectura.texto;
  elemento('consejo').textContent = lectura.consejo;
  elemento('cantidad').textContent = `${lectura.texto.split(/\s+/u).length} palabras · 15–25 s`;
  return lectura;
}

function botones() {
  grabar.disabled = Boolean(activa) || tomas.length >= MAX_TOMAS;
  parar.disabled = !activa || activa.estado === 'finalizando';
  parar.textContent = activa?.estado === 'solicitando' ? 'Cancelar' : 'Detener';
  selector.disabled = Boolean(activa);
  document.body.classList.toggle('grabando', activa?.estado === 'grabando');
}

function mostrarError(mensaje) {
  error.textContent = mensaje;
  error.hidden = false;
}

function mensajeError(fallo) {
  const mensajes = {
    NotAllowedError: 'No se concedió acceso al micrófono. Revisa el permiso de este sitio en el navegador y vuelve a pulsar Grabar.',
    NotFoundError: 'No se encontró un micrófono. Conecta uno y vuelve a intentarlo.',
    NotReadableError: 'El micrófono está ocupado o no se puede leer. Revisa otras aplicaciones y vuelve a intentarlo.',
    OverconstrainedError: 'Este micrófono no acepta los ajustes solicitados. Prueba otro micrófono desde la configuración del navegador.',
    SecurityError: 'El navegador bloqueó el micrófono. Abre esta página directamente en la dirección local de FilmCode.',
  };
  return mensajes[fallo?.name] || fallo?.message || 'No se pudo grabar. Revisa el micrófono y vuelve a intentarlo.';
}

function detenerEntrada(captura) {
  clearInterval(captura.reloj);
  clearTimeout(captura.limite);
  for (const pista of captura.flujo?.getTracks() || []) {
    pista.onended = null;
    pista.stop();
  }
  try { captura.fuente?.disconnect(); } catch { /* Puede haberse desconectado antes. */ }
}

async function liberar(captura) {
  detenerEntrada(captura);
  if (captura.nodo) {
    captura.nodo.port.onmessage = null;
    captura.nodo.onprocessorerror = null;
    try { captura.nodo.disconnect(); } catch { /* Liberación repetida al salir. */ }
    captura.nodo.port.close();
  }
  if (captura.contexto && captura.contexto.state !== 'closed') {
    await captura.contexto.close().catch(() => {});
  }
}

async function comenzar() {
  if (activa || tomas.length >= MAX_TOMAS) return;
  for (const reproduccion of document.querySelectorAll('audio')) reproduccion.pause();
  error.hidden = true;
  const AudioLocal = window.AudioContext || window.webkitAudioContext;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !AudioLocal || !window.AudioWorkletNode) {
    mostrarError('Este navegador no permite grabar aquí. Usa una versión reciente de Chrome, Edge o Firefox y abre la dirección local de FilmCode (127.0.0.1 o localhost).');
    return;
  }
  const captura = {
    numero: ++secuencia, lectura: elegir(), fecha: new Date(), estado: 'solicitando',
    bloques: [], muestras: 0, pico: 0, ultimoAviso: -1,
  };
  captura.fin = new Promise((resolver) => { captura.resolverFin = resolver; });
  activa = captura;
  botones();
  estado.textContent = 'Preparando el micrófono. Si aparece el permiso del navegador, elige Permitir.';
  reloj.textContent = '00:00';
  progreso.value = 0;
  nivel.value = 0;
  try {
    captura.contexto = new AudioLocal();
    if (!captura.contexto.audioWorklet) throw new Error('Este navegador no dispone de AudioWorklet. Prueba una versión reciente de Chrome, Edge o Firefox.');
    await captura.contexto.resume();
    await captura.contexto.audioWorklet.addModule(new URL('./procesador.js', import.meta.url));
    if (activa !== captura) return;
    captura.flujo = await navigator.mediaDevices.getUserMedia({
      video: false,
      audio: { channelCount: { ideal: 1 }, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
    if (activa !== captura) { await liberar(captura); return; }
    captura.frecuencia = captura.contexto.sampleRate;
    captura.nodo = new AudioWorkletNode(captura.contexto, 'grabador-mono', {
      numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1],
    });
    captura.nodo.port.onmessage = ({ data }) => {
      if (activa !== captura) return;
      if (data.tipo === 'muestras') {
        captura.bloques.push(data.muestras);
        captura.muestras += data.muestras.length;
        captura.pico = Math.max(captura.pico, data.pico);
        nivel.value = Math.min(1, data.pico);
      } else if (data.tipo === 'fin') {
        captura.resolverFin(true);
        if (data.motivo === 'limite' && captura.estado === 'grabando') void detener('limite');
      }
    };
    captura.nodo.onprocessorerror = () => void fallar(captura, 'Se interrumpió el procesador de audio. El micrófono se ha detenido; repite la toma.');
    captura.fuente = captura.contexto.createMediaStreamSource(captura.flujo);
    captura.fuente.connect(captura.nodo);
    captura.nodo.connect(captura.contexto.destination);
    for (const pista of captura.flujo.getAudioTracks()) pista.onended = () => void detener('dispositivo');
    captura.estado = 'grabando';
    captura.inicio = performance.now();
    captura.reloj = setInterval(() => actualizarTiempo(captura), 200);
    captura.limite = setTimeout(() => void detener('limite'), 30000);
    estado.textContent = 'Grabando. Lee con naturalidad y pulsa Detener cuando termines.';
    elemento('reloj-accesible').textContent = 'Grabación iniciada.';
    botones();
    elemento('texto').scrollIntoView({ block: 'start', behavior: 'auto' });
  } catch (fallo) {
    await liberar(captura);
    if (activa !== captura) return;
    activa = null;
    botones();
    estado.textContent = 'El micrófono está detenido.';
    mostrarError(mensajeError(fallo));
  }
}

function actualizarTiempo(captura) {
  const segundos = Math.min(30, (performance.now() - captura.inicio) / 1000);
  reloj.textContent = `00:${Math.floor(segundos).toString().padStart(2, '0')}`;
  progreso.value = segundos;
  const intervalo = Math.floor(segundos / 5);
  if (intervalo > captura.ultimoAviso && intervalo > 0) {
    captura.ultimoAviso = intervalo;
    elemento('reloj-accesible').textContent = `${intervalo * 5} segundos grabados.`;
  }
}

async function fallar(captura, mensaje) {
  if (activa !== captura) return;
  activa = null;
  await liberar(captura);
  botones();
  nivel.value = 0;
  estado.textContent = 'El micrófono está detenido.';
  mostrarError(mensaje);
}

async function detener(motivo = 'usuario') {
  const captura = activa;
  if (!captura || captura.estado === 'finalizando') return;
  if (captura.estado === 'solicitando') {
    activa = null;
    await liberar(captura);
    botones();
    estado.textContent = 'Solicitud cancelada. Si el navegador aún muestra el permiso, puedes cerrarlo.';
    return;
  }
  captura.estado = 'finalizando';
  botones();
  detenerEntrada(captura);
  estado.textContent = 'Cerrando el micrófono y preparando el WAV…';
  try {
    captura.nodo.port.postMessage({ tipo: 'parar' });
    let espera;
    const confirmado = await Promise.race([
      captura.fin,
      new Promise((resolver) => { espera = setTimeout(() => resolver(false), 1200); }),
    ]);
    clearTimeout(espera);
    await liberar(captura);
    if (activa !== captura) return;
    if (!confirmado) throw new Error('No se pudo finalizar el audio correctamente. Repite la toma.');
    if (!captura.muestras || captura.pico === 0) throw new Error('No se detectó audio en esta toma. Revisa que el micrófono esté conectado y no esté silenciado.');
    const muestras = new Float32Array(captura.muestras);
    let posicion = 0;
    for (const bloque of captura.bloques) { muestras.set(bloque, posicion); posicion += bloque.length; }
    const wav = crearWav(muestras, captura.frecuencia);
    const duracion = captura.muestras / captura.frecuencia;
    agregarToma(captura, wav, duracion, motivo);
    activa = null;
    nivel.value = 0;
    progreso.value = duracion;
    reloj.textContent = `00:${Math.floor(duracion).toString().padStart(2, '0')}`;
    estado.textContent = `${motivo === 'limite' ? 'Se alcanzó el límite de 30 segundos. ' : ''}Toma conservada. El micrófono está detenido. Escúchala y descarga sus archivos.`;
    if (tomas.length >= MAX_TOMAS) estado.textContent += ' Alcanzaste las 20 tomas de esta sesión. Descárgalas antes de abrir una nueva sesión.';
    botones();
    grabar.focus();
  } catch (fallo) {
    await fallar(captura, mensajeError(fallo));
  }
}

function crearElemento(etiqueta, texto, clase) {
  const nodo = document.createElement(etiqueta);
  if (texto) nodo.textContent = texto;
  if (clase) nodo.className = clase;
  return nodo;
}

function agregarToma(captura, wav, duracion, motivo) {
  const fechaId = captura.fecha.toISOString().replace(/[-:]/gu, '').replace(/\.\d{3}Z$/u, 'Z');
  const id = `voz-${captura.lectura.id}-${fechaId}-${String(captura.numero).padStart(2, '0')}`;
  const toma = { id, wavUrl: URL.createObjectURL(new Blob([wav], { type: 'audio/wav' })), txtUrl: '', audioDescargado: false, textoDescargado: false };
  tomas.push(toma);
  const tarjeta = crearElemento('article', '', 'toma');
  const titulo = crearElemento('h3', `${captura.lectura.titulo} · toma ${captura.numero}`);
  titulo.id = `${id}-titulo`;
  tarjeta.setAttribute('aria-labelledby', titulo.id);
  tarjeta.append(titulo);
  const fecha = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'medium' }).format(captura.fecha);
  tarjeta.append(crearElemento('p', `${fecha} · ${duracion.toFixed(1)} s · ${captura.frecuencia} Hz · mono · PCM16`, 'nota'));
  if (duracion < 15 || duracion > 25 || motivo === 'dispositivo') {
    tarjeta.append(crearElemento('p', motivo === 'dispositivo' ? 'El micrófono se desconectó. Revisa si la lectura quedó completa.' : 'La duración quedó fuera del objetivo de 15–25 segundos. Escucha si la lectura está completa y repítela si lo necesitas.', 'aviso'));
  }
  if (captura.pico >= 0.99) tarjeta.append(crearElemento('p', 'Se detectó un nivel cercano al máximo. Escucha si hay distorsión; puedes repetir un poco más lejos del micrófono.', 'aviso'));
  const reproductor = crearElemento('audio');
  reproductor.controls = true;
  reproductor.preload = 'metadata';
  reproductor.src = toma.wavUrl;
  reproductor.setAttribute('aria-label', `Escuchar ${captura.lectura.titulo}, toma ${captura.numero}`);
  tarjeta.append(reproductor);
  const detalles = crearElemento('details');
  detalles.append(crearElemento('summary', 'Revisar la transcripción de esta toma'));
  const etiqueta = crearElemento('label', 'Texto pronunciado (corrige aquí si cambiaste alguna palabra)');
  etiqueta.htmlFor = `${id}-texto`;
  const transcripcion = crearElemento('textarea');
  transcripcion.id = etiqueta.htmlFor;
  transcripcion.rows = 4;
  transcripcion.value = captura.lectura.texto;
  transcripcion.spellcheck = true;
  detalles.append(etiqueta, transcripcion);
  tarjeta.append(detalles);
  const acciones = crearElemento('div', '', 'acciones');
  const audio = crearElemento('a', 'Descargar WAV', 'boton');
  audio.href = toma.wavUrl;
  audio.download = `${id}.wav`;
  audio.addEventListener('click', () => { toma.audioDescargado = true; });
  const txt = crearElemento('a', 'Descargar TXT', 'boton');
  txt.download = `${id}.txt`;
  const actualizarTxt = () => {
    if (toma.txtUrl) URL.revokeObjectURL(toma.txtUrl);
    toma.txtUrl = URL.createObjectURL(new Blob([transcripcion.value], { type: 'text/plain;charset=utf-8' }));
    txt.href = toma.txtUrl;
    toma.textoDescargado = false;
  };
  actualizarTxt();
  transcripcion.addEventListener('input', actualizarTxt);
  txt.addEventListener('click', () => { toma.textoDescargado = true; });
  acciones.append(audio, txt);
  tarjeta.append(acciones, crearElemento('p', id, 'identificador'));
  elemento('lista-tomas').prepend(tarjeta);
  elemento('vacio').hidden = true;
  elemento('total-tomas').textContent = `${tomas.length} ${tomas.length === 1 ? 'toma' : 'tomas'}`;
}

selector.addEventListener('change', elegir);
grabar.addEventListener('click', () => void comenzar());
parar.addEventListener('click', () => void detener());
window.addEventListener('beforeunload', (evento) => {
  if (activa || tomas.some((toma) => !toma.audioDescargado || !toma.textoDescargado)) {
    if (activa) void detener('salida');
    evento.preventDefault();
    evento.returnValue = '';
  }
});
window.addEventListener('pagehide', (evento) => {
  if (activa) {
    void liberar(activa);
    activa = null;
    botones();
    estado.textContent = 'La grabación se detuvo al salir de la página.';
  }
  for (const audio of document.querySelectorAll('audio')) audio.pause();
  if (!evento.persisted) {
    for (const toma of tomas) {
      URL.revokeObjectURL(toma.wavUrl);
      URL.revokeObjectURL(toma.txtUrl);
    }
  }
});
elegir();
botones();
