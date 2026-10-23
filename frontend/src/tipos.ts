export type Calidad = string;
export type CalidadRender = '480p30' | '480p60' | '720p30' | '720p60' | '1080p30' | '1080p60';
export type Json = string | number | boolean | null | Json[] | { [clave: string]: Json };
export type Objeto = { [clave: string]: Json };
export interface Escena extends Objeto { tipo: string }
export interface Guion { version?: number; titulo: string; escenas: Escena[]; fragmentos?: Record<string, {archivo: string; desde?: number; hasta?: number; lenguaje?: string; traza?: string}>; [clave: string]: unknown }
export interface Trabajo { id: string; proyecto: string; tipo: string; calidad?: Calidad; estado: 'corriendo' | 'terminado' | 'error' | 'cancelado' | 'interrumpido'; inicio: string; fin?: string; progreso: number | null; mensaje: string; error?: string; lineas: string[]; externo?: boolean; prioridad_baja?: boolean | null }
export interface EstadoRecursos { activo: boolean; perfil: 'baja' | 'alta' | null; limite_cpu: number | null; aplicado: boolean; ram_libre_gib: number; reserva_ram_gib: number; proteccion_ram: boolean; pausado: boolean; mensaje: string; servicios: string[]; errores: string[] }
export interface Video { calidad: Calidad; duracion: number; megas: number; fecha: string; desactualizado: boolean; segundos_render?: number; animaciones?: number; voz?: ProveedorVoz; resolucion?: number; fps?: number }
export type Situacion = 'listo' | 'en_curso' | 'en_curso_externo' | 'interrumpido' | 'error';
export interface Proyecto { nombre: string; titulo: string; tipo: string; etapa: string; mensaje: string; progreso: number | null; actualizado: string; tiene_guion: boolean; tiene_guion_con_errores?: boolean; videos: Video[]; situacion: Situacion; trabajo: Trabajo | null; miniatura?: string; archivos?: Record<string, boolean>; preferencias?: Partial<OpcionesTrabajo> }
export type FaseRender = 'voces' | 'animaciones' | 'exportacion' | 'terminado';
export interface ProgresoVoces { textos?: number; cacheados?: number; generados?: number; pendientes?: number; fallidas?: number; omitidas?: number; fallos?: string[]; subfase?: 'audio' | 'sincronizacion' | 'completo'; audios_preparados?: number }
export interface Detalle extends Proyecto { manifiesto: { nombre: string; titulo: string; creado?: string; fuente: { tipo: string; copia: string; original?: string } }; estado: { etapa: string; mensaje: string; progreso: number | null; fase_render?: FaseRender; historial?: {etapa: string; fecha: string}[]; salidas?: Record<string, Video>; guion?: { escenas?: number; caracteres?: number; modelo?: string; segundos?: number; duracion_estimada_segundos?: number; duracion_objetivo_minutos?: number | null }; voces?: ProgresoVoces | null } }
export interface Servicio { listo: boolean; mensaje: string }
export interface Salud { ollama: Servicio & { modelos: string[]; cargados?: string[] }; voicestudio: Servicio; ffmpeg: boolean; trabajo: Trabajo | null }
export type ProveedorVoz = 'voicestudio' | 'edge' | 'silencio';
export interface Voz { id: string; nombre: string; acento?: string; genero?: string }
export interface Voces { edge: Voz[]; voicestudio: Voz[] | { error: string } }
export interface Ajustes { modelo: { proveedor: string; modelo: string; url: string; temperatura: number; contexto: number; max_tokens: number; formato: string }; voz: { proveedor: string; voicestudio_url: string; voicestudio_voz: string; voicestudio_modelo: string; voicestudio_idioma: string; edge_voz: string; edge_velocidad: string }; claves: { openai: boolean; voicestudio: boolean }; capacidades?: { prioridad_dinamica: boolean; rutas_anfitrion: boolean; modo: 'docker' | 'nativo' } }
export interface PerfilCalidad { banderas: string[]; voz: 'silencio' | 'edge' | 'voicestudio' | string; carpeta: string; resolucion?: number; fps?: number; ancho?: number }
export interface Esquema { escenas: Record<string, string[]>; acciones: Record<string, unknown>; iconos: string[]; limites: { texto: number; escenas: number; lineas: number; archivos: number; bytes: number }; calidades: Record<Calidad, PerfilCalidad>; calidad_predeterminada?: CalidadRender }
export interface Archivo { ruta: string; bytes: number; lenguaje: string; lineas?: number }
export interface Revision { existe: boolean; tipo: string | null; archivos: Archivo[]; total: number; bytes?: number; lineas?: number; ignorados?: {ruta: string; motivo: string}[] }
export interface Narrado { duracion_total: number; caracteres: number; bloques: {inicio: number; duracion: number; texto: string; proveedor: string}[]; capitulos: {escena: number; tipo: string; titulo: string; inicio: number}[] }
export interface OpcionesTrabajo { tipo: 'guion' | 'render' | 'continuar' | 'fotogramas'; calidad?: Calidad; modelo?: string; capturar?: boolean; prioridad_baja?: boolean; duracion_objetivo_minutos?: number | null; velocidad_voz?: number; velocidad_animaciones?: number; voz_fluida?: boolean; voz?: ProveedorVoz; voz_edge?: string; voz_voicestudio?: string }
