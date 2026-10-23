import type { Ajustes, CalidadRender, Escena, Guion, Json, Narrado, OpcionesTrabajo, PerfilCalidad, Proyecto, ProveedorVoz, Situacion, Voces } from './tipos';

const CALIDADES_RENDER: CalidadRender[] = ['480p30', '480p60', '720p30', '720p60', '1080p30', '1080p60'];
const FORMATOS_LEGACY: Record<string, string> = { borrador: '480p15', silencio: '480p15', alta: '1080p30', final: '1080p30', final60: '720p60' };
export const AYUDA_PRIORIDAD = 'Baja habilita menos procesadores de CPU; Alta habilita más. El estado muestra la capacidad asignada y el margen de memoria. La GPU no tiene un tope porcentual.';

export function configRenderInicial(calidad?: string): CalidadRender {
  const formato = FORMATOS_LEGACY[calidad ?? ''] ?? calidad;
  return CALIDADES_RENDER.find(c => c === formato) ?? (formato === '480p15' ? '480p30' : '720p30');
}

export function nombreValido(texto: string) { return texto.normalize('NFKD').replace(/[^\x00-\x7F]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'video'; }
export function duracion(segundos: number) {
  const s = Math.max(0, Math.round(segundos)), dos = (n: number) => String(n).padStart(2, '0');
  return s >= 3600 ? `${Math.floor(s / 3600)}:${dos(Math.floor(s / 60) % 60)}:${dos(s % 60)}` : `${dos(Math.floor(s / 60))}:${dos(s % 60)}`;
}
export function fecha(texto?: string) { return texto ? new Date(texto).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }) : '—'; }
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic'];
export function fechaCorta(texto?: string) {
  if (!texto) return '—';
  const d = new Date(texto);
  return Number.isNaN(d.getTime()) ? '—' : `${d.getDate()} ${MESES[d.getMonth()]}, ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
export function numero(valor: number, decimales = 1) { return valor.toLocaleString('es-CO', { maximumFractionDigits: decimales }); }
export function tiempoLegible(segundos: number) {
  const minutos = Math.max(1, Math.round(segundos / 60));
  if (minutos < 60) return `${minutos} min`;
  const horas = Math.floor(minutos / 60), resto = minutos % 60;
  return resto ? `${horas} h ${resto} min` : `${horas} h`;
}
export function describirCalidad(calidad: string, perfil?: PerfilCalidad, voz?: string) {
  const formato = perfil?.carpeta ?? FORMATOS_LEGACY[calidad] ?? calidad;
  const coincidencia = /^(\d+)p(\d+)$/.exec(formato);
  const alto = perfil?.resolucion ?? (coincidencia ? Number(coincidencia[1]) : undefined);
  const fps = perfil?.fps ?? (coincidencia ? Number(coincidencia[2]) : undefined);
  const imagen = alto && fps ? `${alto}p · ${fps} FPS` : formato;
  return { nombre: imagen, detalle: voz === undefined && perfil ? `${imagen} · ${describirVoz(perfil.voz)}` : imagen };
}
export function describirVoz(proveedor: string) {
  return proveedor === 'silencio' ? 'sin voz' : proveedor === 'edge' ? 'voz de Edge (internet)' : 'tu voz en VoiceStudio';
}

// La voz se elige como el modelo: un solo selector con valores «proveedor:id» (o «silencio»).
export function separarVoz(valor: string): { proveedor: ProveedorVoz; id: string } {
  const [proveedor, ...resto] = valor.split(':');
  return { proveedor: proveedor === 'edge' || proveedor === 'silencio' ? proveedor : 'voicestudio', id: resto.join(':') };
}
export function vozInicial(ajustes: Ajustes, preferencias?: Partial<OpcionesTrabajo>) {
  const proveedor = preferencias?.voz ?? 'voicestudio';
  if (proveedor === 'silencio') return 'silencio';
  if (proveedor === 'edge') return `edge:${preferencias?.voz_edge || ajustes.voz.edge_voz}`;
  return `voicestudio:${preferencias?.voz_voicestudio || ajustes.voz.voicestudio_voz}`;
}
export function opcionesVoz(ajustes?: Ajustes, voces?: Voces) {
  const propia = ajustes?.voz.voicestudio_voz ?? '';
  const locales = Array.isArray(voces?.voicestudio) ? voces.voicestudio.filter(v => v.id !== propia) : [];
  return [
    { valor: `voicestudio:${propia}`, texto: 'Tu voz', detalle: 'VoiceStudio · la primera vez tarda horas' },
    ...locales.map(v => ({ valor: `voicestudio:${v.id}`, texto: v.nombre, detalle: 'VoiceStudio' })),
    ...(voces?.edge ?? []).map(v => ({ valor: `edge:${v.id}`, texto: v.nombre, detalle: `Edge · ${v.acento ?? ''} · rápida, con internet` })),
    { valor: 'silencio', texto: 'Sin voz', detalle: 'solo la imagen, para revisar' },
  ];
}
export function opcionesDeVoz(valor: string): Pick<OpcionesTrabajo, 'voz' | 'voz_edge' | 'voz_voicestudio'> {
  const { proveedor, id } = separarVoz(valor);
  return proveedor === 'edge' ? { voz: 'edge', voz_edge: id } : proveedor === 'voicestudio' ? { voz: 'voicestudio', voz_voicestudio: id } : { voz: 'silencio' };
}
export function estadoProyecto(p: Pick<Proyecto, 'situacion' | 'etapa' | 'videos'>): { texto: string; color: 'verde' | 'amarillo' | 'rojo' | 'gris' } {
  const textos: Record<Situacion, string> = { listo: p.etapa, en_curso: 'en curso', en_curso_externo: 'en curso', interrumpido: 'interrumpido', error: 'error' };
  if (p.situacion === 'error' || p.etapa === 'error') return { texto: 'error', color: 'rojo' };
  if (p.situacion !== 'listo') return { texto: textos[p.situacion], color: 'amarillo' };
  if (p.videos.length && !p.videos.some(v => !v.desactualizado)) return { texto: 'desactualizado', color: 'amarillo' };
  return p.videos.length ? { texto: 'terminado', color: 'verde' } : { texto: p.etapa, color: 'gris' };
}
export function objeto(valor: Json | undefined): valor is Record<string, Json> { return valor !== null && typeof valor === 'object' && !Array.isArray(valor); }
export interface Narracion { ruta: (string | number)[]; texto: string }
export function narraciones(escena: Escena): Narracion[] {
  const salida: Narracion[] = [];
  const agregar = (valor: Json | undefined, ruta: (string | number)[]) => { if (typeof valor === 'string') salida.push({ ruta, texto: valor }); };
  if (Array.isArray(escena.narracion)) escena.narracion.forEach((v, i) => agregar(v, ['narracion', i]));
  for (const campo of ['intro', 'cierre', 'resultado', 'reto']) agregar(escena[campo], [campo]);
  for (const campo of ['bloques', 'items', 'lineas']) {
    const lista = escena[campo];
    if (Array.isArray(lista)) lista.forEach((v, i) => objeto(v) ? agregar(v.texto, [campo, i, 'texto']) : agregar(v, [campo, i]));
  }
  if (Array.isArray(escena.comandos)) escena.comandos.forEach((comando, i) => {
    if (!objeto(comando)) return;
    agregar(comando.texto, ['comandos', i, 'texto']); agregar(comando.texto_salida, ['comandos', i, 'texto_salida']);
    if (Array.isArray(comando.partes)) comando.partes.forEach((parte, j) => { if (objeto(parte)) agregar(parte.texto, ['comandos', i, 'partes', j, 'texto']); });
  });
  return salida;
}
export function cambiarNarracion(escena: Escena, ruta: (string | number)[], texto: string): Escena {
  const copia = structuredClone(escena);
  let actual: Json = copia;
  for (const clave of ruta.slice(0, -1)) actual = Array.isArray(actual) ? actual[Number(clave)] : (actual as Record<string, Json>)[String(clave)];
  const ultima = ruta[ruta.length - 1];
  if (Array.isArray(actual)) actual[Number(ultima)] = texto; else (actual as Record<string, Json>)[String(ultima)] = texto;
  return copia;
}
export function siguiente(proyecto: Proyecto) {
  if (proyecto.situacion === 'en_curso' || proyecto.situacion === 'en_curso_externo') return 'cancelar';
  if (proyecto.situacion === 'interrumpido') return 'retomar';
  if (proyecto.situacion === 'error' || proyecto.etapa === 'error') return 'reintentar';
  if (!proyecto.tiene_guion) return proyecto.tiene_guion_con_errores || proyecto.archivos?.guion_con_errores ? 'corregir' : 'guion';
  return proyecto.videos.some(v => !v.desactualizado) ? 'ver' : 'render';
}
export function srtAVtt(texto: string) { return `WEBVTT\n\n${texto.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/(\d{2}:\d{2}:\d{2}),(\d{3})/g, '$1.$2')}`; }
export function capitulos(guion: Guion, bloques: Narrado['bloques']): Narrado['capitulos'] {
  const textos = guion.escenas.map(escena => narraciones(escena).map(n => n.texto.replace(/\[\[.*?\]\]/g, '').trim()));
  const salida: Narrado['capitulos'] = [];
  let actual = 0;
  for (const bloque of bloques) {
    const encontrada = textos.findIndex((frases, i) => i >= actual && frases.includes(bloque.texto));
    if (encontrada < 0) continue;
    actual = encontrada;
    if (!salida.some(c => c.escena === actual + 1)) salida.push({ escena: actual + 1, tipo: guion.escenas[actual].tipo, titulo: String(guion.escenas[actual].titulo ?? `Escena ${actual + 1}`), inicio: bloque.inicio });
  }
  return salida;
}
