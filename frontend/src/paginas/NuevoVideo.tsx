import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { Check, ChevronRight } from 'lucide-react';
import { baseProyecto, enviar, peticion, refrescarSalud, useDatos } from '../api';
import type { Ajustes, Orientacion, Revision, Salud, Voces } from '../tipos';
import { AYUDA_PRIORIDAD, VELOCIDAD_VOZ_PREDETERMINADA, configRenderInicial, describirCalidad, describirVoz, duracion, nombreValido, numero, opcionesDeVoz, opcionesVoz, separarVoz, vozInicial } from '../logica';
import { archivosArrastrados, filtrarSubidas } from '../fuentes';
import type { Subida } from '../fuentes';
import { avisar, Mensaje, navegarPestanas } from '../componentes/Comun';
import { Interruptor, Selector } from '../componentes/Controles';
import { OpcionesRender } from '../componentes/OpcionesRender';
import { FONDO_PREDETERMINADO, nombreFondoVideo } from '../componentes/FondoVideo';

type Modo = 'archivos' | 'ruta' | 'markdown';
const MODOS: [Modo, string][] = [['archivos', 'Archivo o carpeta'], ['ruta', 'Ruta local'], ['markdown', 'Guía en Markdown']];
const EXTENSIONES_REFERENCIA = '.png,.jpg,.jpeg,.webp,.mp4,.webm,.mov,.mkv';
const MIB = 1024 * 1024;

function errorReferenciaVisual(archivo: File | null) {
  if (!archivo) return '';
  const imagen = /\.(png|jpe?g|webp)$/i.test(archivo.name);
  if (!imagen && !/\.(mp4|webm|mov|mkv)$/i.test(archivo.name)) return 'Elige una imagen PNG, JPG o WebP, o un video MP4, WebM, MOV o MKV.';
  if (!archivo.size) return 'El archivo está vacío.';
  const maximo = imagen ? 20 : 200;
  if (archivo.size > maximo * MIB) return `La referencia supera el límite de ${maximo} MiB.`;
  return '';
}

export function NuevoVideo() {
  const [parametros] = useSearchParams();
  const { state } = useLocation() as { state: { subidas?: Subida[] } | null };
  const [modo, setModo] = useState<Modo>(state?.subidas ? 'archivos' : parametros.get('ruta') ? 'ruta' : 'archivos');
  const [subidas, setSubidas] = useState<Subida[]>(state?.subidas ?? []), [ruta, setRuta] = useState(parametros.get('ruta') ?? ''), [markdown, setMarkdown] = useState('');
  const [referencia, setReferencia] = useState<File | null>(null);
  const [revision, setRevision] = useState<Revision | null>(null);
  const [nombre, setNombre] = useState(''), [titulo, setTitulo] = useState(''), [calidad, setCalidad] = useState<string>(() => configRenderInicial());
  const [orientacion, setOrientacion] = useState<Orientacion>('horizontal');
  const [fondoVideo, setFondoVideo] = useState(FONDO_PREDETERMINADO);
  const [modelo, setModelo] = useState(''), [voz, setVoz] = useState('');
  const [capturar, setCapturar] = useState(false), [prioridad, setPrioridad] = useState(true);
  const [duracionObjetivo, setDuracionObjetivo] = useState('');
  const [entradaDuracionInvalida, setEntradaDuracionInvalida] = useState(false);
  const [velocidadVoz, setVelocidadVoz] = useState(String(VELOCIDAD_VOZ_PREDETERMINADA)), [velocidadAnimaciones, setVelocidadAnimaciones] = useState('1');
  const [entradaVelocidadVozInvalida, setEntradaVelocidadVozInvalida] = useState(false), [entradaVelocidadAnimacionesInvalida, setEntradaVelocidadAnimacionesInvalida] = useState(false);
  const [vozFluida, setVozFluida] = useState(true);
  const [ocupado, setOcupado] = useState(false), [revisando, setRevisando] = useState(false), [soltando, setSoltando] = useState(false), [creado, setCreado] = useState('');
  const salud = useDatos<Salud>('/salud', 10000), ajustes = useDatos<Ajustes>('/ajustes'), voces = useDatos<Voces>('/voces');
  const enDocker = ajustes.data?.capacidades?.modo === 'docker';
  const prioridadDinamica = ajustes.data?.capacidades?.prioridad_dinamica !== false;
  const rutasAnfitrion = ajustes.data?.capacidades?.rutas_anfitrion !== false;
  const navegar = useNavigate(), cliente = useQueryClient();
  const carpeta = useRef<HTMLInputElement>(null);
  const entradaReferencia = useRef<HTMLInputElement>(null);
  const archivos = filtrarSubidas(subidas);
  useEffect(() => { carpeta.current?.setAttribute('webkitdirectory', ''); }, [modo]);
  useEffect(() => { if (ajustes.data) { setModelo(m => m || `${ajustes.data.modelo.proveedor}:${ajustes.data.modelo.modelo}`); setVoz(v => v || vozInicial(ajustes.data)); } }, [ajustes.data]);
  useEffect(() => { if (state?.subidas?.length) sugerir(state.subidas[0].ruta.split('/')[0]); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (parametros.get('ruta')) void revisar(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function sugerir(texto: string) { const base = texto.replace(/\.[^.]+$/, ''); setNombre(n => n || nombreValido(base).replace(/-+$/, '')); setTitulo(t => t || base.slice(0, 200)); }
  function elegir(lista: Subida[]) { setSubidas(lista); setCreado(''); if (lista[0]) sugerir(lista[0].ruta.split('/')[0]); }
  function adjuntarReferencia(archivo: File | null) {
    setReferencia(archivo);
    setCreado('');
    if (archivo) setCapturar(false);
  }
  async function revisar() {
    if (!ruta.trim()) return;
    setRevisando(true);
    try { const r = await enviar<Revision>('/fuentes/revisar', { ruta: ruta.trim() }); setRevision(r); if (r.existe) sugerir(ruta.trim().split(/[\\/]/).filter(Boolean).at(-1) ?? 'video'); }
    catch (e) { setRevision(null); avisar((e as Error).message, true); } finally { setRevisando(false); }
  }
  const fuentePrincipalLista = modo === 'archivos' ? archivos.archivos.length > 0 : modo === 'ruta' ? Boolean(revision?.existe && revision.archivos.length) : Boolean(markdown.trim()) && new TextEncoder().encode(markdown).length <= 400_000;
  const errorReferencia = errorReferenciaVisual(referencia);
  const fuenteLista = fuentePrincipalLista && !errorReferencia;
  const nombreBien = Boolean(nombre) && nombreValido(nombre) === nombre;
  const minutosObjetivo = duracionObjetivo.trim() === '' ? null : Number(duracionObjetivo);
  const duracionValida = !entradaDuracionInvalida && (minutosObjetivo == null || (Number.isFinite(minutosObjetivo) && minutosObjetivo >= 1 && minutosObjetivo <= 120));
  const factorVoz = Number(velocidadVoz), factorAnimaciones = Number(velocidadAnimaciones);
  const velocidadVozValida = !entradaVelocidadVozInvalida && velocidadVoz.trim() !== '' && Number.isFinite(factorVoz) && factorVoz >= 0.75 && factorVoz <= 1.5;
  const velocidadAnimacionesValida = !entradaVelocidadAnimacionesInvalida && velocidadAnimaciones.trim() !== '' && Number.isFinite(factorAnimaciones) && factorAnimaciones >= 0.5 && factorAnimaciones <= 2;
  const velocidadesValidas = velocidadVozValida && velocidadAnimacionesValida;
  const nombreModelo = modelo.replace(/^ollama:/, '');
  const modeloInstalado = Boolean(salud.data?.ollama.modelos.some(m => m === nombreModelo || m === `${nombreModelo}:latest`));
  const proveedor = voz ? separarVoz(voz).proveedor : 'voicestudio', necesitaVoiceStudio = proveedor === 'voicestudio';
  const nombreVoz = opcionesVoz(ajustes.data, voces.data).find(opcion => opcion.valor === voz)?.texto ?? describirVoz(proveedor);
  const impedimento = salud.isPending ? 'Consultando los servicios de este equipo…' : salud.error ? 'No hay conexión con la API local.'
    : salud.data?.trabajo ? `Ya hay un trabajo en marcha en ${salud.data.trabajo.proyecto}: espera a que termine.`
    : !salud.data?.ollama.listo ? salud.data?.ollama.mensaje ?? 'Ollama no responde.'
    : !modeloInstalado ? `Ollama no tiene ${nombreModelo || 'el modelo elegido'}. Elige otro en Avanzado.`
    : necesitaVoiceStudio && !salud.data?.voicestudio.listo ? salud.data?.voicestudio.mensaje ?? 'VoiceStudio no responde.'
    : !salud.data?.ffmpeg ? 'No se encuentra ffmpeg en este equipo.' : '';
  const paso = !fuenteLista ? 0 : !nombreBien ? 1 : 2;

  async function crear(evento: FormEvent) {
    evento.preventDefault();
    if (ocupado || impedimento || !fuenteLista || !nombreBien || !duracionValida || !velocidadesValidas) return;
    setOcupado(true);
    try {
      let proyecto = creado;
      if (!proyecto) {
        let resultado: {nombre: string};
        if (modo === 'archivos' || referencia) {
          const formulario = new FormData();
          if (modo === 'archivos') archivos.archivos.forEach(s => formulario.append('archivos', s.archivo, s.ruta));
          if (modo === 'ruta') formulario.append('ruta', ruta.trim());
          if (modo === 'markdown') {
            formulario.append('markdown', markdown);
            formulario.append('archivo', 'guia.md');
          }
          if (referencia) formulario.append('referencia_visual', referencia);
          formulario.append('nombre', nombre);
          formulario.append('titulo', titulo);
          resultado = await peticion(referencia ? '/proyectos/con-referencia' : '/proyectos', { method: 'POST', body: formulario });
        } else {
          resultado = await enviar('/proyectos', { ...(modo === 'ruta' ? { ruta: ruta.trim() } : { markdown, archivo: 'guia.md' }), nombre, titulo });
        }
        proyecto = resultado.nombre; setCreado(proyecto);
      }
      await enviar(`${baseProyecto(proyecto)}/trabajos`, { tipo: 'continuar', calidad, orientacion, fondo_video: fondoVideo, modelo, capturar: !referencia && capturar, prioridad_baja: prioridad, duracion_objetivo_minutos: minutosObjetivo, velocidad_voz: factorVoz, velocidad_animaciones: factorAnimaciones, voz_fluida: vozFluida, ...opcionesDeVoz(voz) });
      await cliente.invalidateQueries(); navegar(`/proyectos/${proyecto}`);
    } catch (e) { avisar((e as Error).message, true); } finally { setOcupado(false); }
  }

  return <form className="vc-pagina" onSubmit={e => void crear(e)}>
    <div className="vc-cabeza">
      <div>
        <h1 className="titulo">Nuevo video</h1>
        <p className="vc-cabeza__meta">Convierte código o una guía en una explicación animada. Añade una referencia si quieres orientar el estilo visual.</p>
      </div>
    </div>
    <div className="vc-nuevo">
      <div className="vc-nuevo__pasos">
        <section className="vc-nuevo__paso" aria-labelledby="paso-fuente">
          <h2 id="paso-fuente" className="vc-nuevo__linea" aria-current={paso === 0 ? 'step' : undefined}>{paso > 0 && <Check aria-hidden="true"/>}Fuente</h2>
          <div className="vc-pestanas" role="tablist" aria-label="Fuente principal" onKeyDown={navegarPestanas}>
            {MODOS.map(([id, texto]) => <button key={id} type="button" role="tab" className="vc-pestana" aria-selected={modo === id} tabIndex={modo === id ? 0 : -1} onClick={() => { setModo(id); setCreado(''); }}>{id === 'ruta' && !rutasAnfitrion ? 'Ruta del contenedor' : texto}</button>)}
          </div>
          {modo === 'archivos' ? <>
            <div className="vc-soltar" data-soltando={soltando ? '' : undefined} onDragOver={e => { e.preventDefault(); setSoltando(true); }} onDragLeave={() => setSoltando(false)}
              onDrop={e => { e.preventDefault(); setSoltando(false); void archivosArrastrados(e.dataTransfer).then(elegir).catch((err: Error) => avisar(err.message, true)); }}>
              <p className="entrada">Arrastra aquí un archivo o una carpeta</p>
              <div className="vc-fila-botones">
                <label className="vc-boton">Elegir archivos<input className="vc-oculto" type="file" multiple onChange={e => elegir(Array.from(e.target.files ?? []).map(archivo => ({ archivo, ruta: archivo.name })))}/></label>
                <label className="vc-boton">Elegir carpeta<input ref={carpeta} className="vc-oculto" type="file" multiple onChange={e => elegir(Array.from(e.target.files ?? []).map(archivo => ({ archivo, ruta: archivo.webkitRelativePath || archivo.name })))}/></label>
              </div>
              <p className="vc-nota">Hasta 400 archivos, 400 KB por archivo y 20 MB en total. Las carpetas como node_modules o .git se saltan solas.</p>
            </div>
            {subidas.length > 0 && <div className="grid gap-3">
              <p className="m-0"><span className="vc-cifras">{archivos.archivos.length}</span> {archivos.archivos.length === 1 ? 'archivo incluido' : 'archivos incluidos'} · <span className="vc-cifras">{numero(archivos.total / 1000)} KB</span></p>
              <ul className="vc-lista-archivos">{archivos.archivos.map(s => <li key={s.ruta}><span>{s.ruta}</span><small>{numero(Math.max(1, s.archivo.size / 1000), 0)} KB</small></li>)}</ul>
              {archivos.ignorados.length > 0 && <details className="vc-plegable"><summary><ChevronRight aria-hidden="true"/>{archivos.ignorados.length} se ignoran</summary><ul className="vc-lista-archivos">{archivos.ignorados.map(s => <li key={s}>{s}</li>)}</ul></details>}
            </div>}
          </> : modo === 'ruta' ? <>
            <div className="vc-campo">
              <label className="vc-campo__etiqueta" htmlFor="ruta">{rutasAnfitrion ? 'Ruta de un archivo o una carpeta de este equipo' : 'Ruta de un archivo o una carpeta dentro del contenedor'}</label>
              <div className="flex gap-3">
                <input id="ruta" className="vc-campo__entrada" placeholder={rutasAnfitrion ? 'C:\\Proyectos\\mi-proyecto' : '/entrada/mi-proyecto'} value={ruta} onChange={e => { setRuta(e.target.value); setRevision(null); setCreado(''); }} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); void revisar(); } }}/>
                <button type="button" className="vc-boton" disabled={!ruta.trim() || revisando} onClick={() => void revisar()}>{revisando ? 'Revisando…' : 'Revisar'}</button>
              </div>
              {!rutasAnfitrion && <span className="vc-campo__ayuda">Docker solo ve los archivos del contenedor y las carpetas montadas. Para usar archivos del equipo sin montar carpetas, elige «Archivo o carpeta».</span>}
            </div>
            {revision && (revision.existe ? <div className="grid gap-3">
              <p className="m-0"><span className="vc-cifras">{revision.total}</span> {revision.total === 1 ? 'archivo' : 'archivos'}{revision.lineas != null && <> · <span className="vc-cifras">{numero(revision.lineas, 0)}</span> líneas</>}</p>
              <ul className="vc-lista-archivos">{revision.archivos.map(a => <li key={a.ruta}><span>{a.ruta}</span><small>{a.lineas ?? '—'} líneas</small></li>)}</ul>
              {Boolean(revision.ignorados?.length) && <details className="vc-plegable"><summary><ChevronRight aria-hidden="true"/>{revision.ignorados?.length} se ignoran</summary><ul className="vc-lista-archivos">{revision.ignorados?.map(a => <li key={a.ruta}><span>{a.ruta}</span><small>{a.motivo}</small></li>)}</ul></details>}
            </div> : <Mensaje tono="aviso">No encuentro esa ruta en este equipo. Revisa que exista.</Mensaje>)}
          </> : <>
            <label className="vc-campo">
              <span className="vc-campo__etiqueta">Tu guía en Markdown</span>
              <textarea className="vc-campo__entrada" rows={12} value={markdown} placeholder="# Cómo instalar…" aria-describedby="guia-markdown-ayuda" onChange={e => { setMarkdown(e.target.value); setCreado(''); if (!nombre) setNombre('mi-guia'); }}/>
            </label>
            <p id="guia-markdown-ayuda" className="vc-nota">Incluye los pasos, comandos o resultados que quieras mostrar. FilmCode usa la guía para preparar demostraciones y explicar qué cambia y por qué.</p>
            {markdown.trim() && <details className="vc-plegable"><summary><ChevronRight aria-hidden="true"/>Vista previa</summary><div className="vc-markdown"><ReactMarkdown skipHtml components={{ img: () => <span>[imagen omitida]</span>, a: ({ children }) => <span>{children}</span> }}>{markdown}</ReactMarkdown></div></details>}
          </>}
          <div className={`vc-campo${errorReferencia ? ' vc-campo--error' : ''}`}>
            <span className="vc-campo__etiqueta">Referencia visual (opcional)</span>
            <div className="vc-fila-botones">
              <button type="button" className="vc-boton" disabled={ocupado} aria-describedby={`referencia-visual-ayuda${errorReferencia ? ' referencia-visual-error' : ''}`} onClick={() => entradaReferencia.current?.click()}>{referencia ? 'Cambiar referencia' : 'Elegir imagen o video'}</button>
              <input ref={entradaReferencia} type="file" hidden accept={EXTENSIONES_REFERENCIA} disabled={ocupado} onChange={e => { const archivo = e.currentTarget.files?.[0]; if (archivo) adjuntarReferencia(archivo); e.currentTarget.value = ''; }}/>
              {referencia && <button type="button" className="vc-boton" disabled={ocupado} onClick={() => adjuntarReferencia(null)}>Quitar referencia</button>}
            </div>
            {referencia && <p className="vc-nota" role="status">{referencia.name} · {numero(referencia.size / MIB, 2)} MiB</p>}
            <span id="referencia-visual-ayuda" className="vc-campo__ayuda">FilmCode usa la referencia para ajustar la paleta y la apariencia. Los pasos del guion salen de tu guía o código. Imágenes PNG, JPG o WebP de hasta 20 MiB; videos MP4, WebM, MOV o MKV de hasta 200 MiB y 15 minutos.</span>
            {errorReferencia && <span id="referencia-visual-error" className="vc-campo__error" role="alert">{errorReferencia}</span>}
            {referencia && !errorReferencia && !fuentePrincipalLista && <p className="vc-nota">Añade código o una guía para indicar qué debe explicar el video.</p>}
          </div>
        </section>
        <section className="vc-nuevo__paso" aria-labelledby="paso-opciones">
          <h2 id="paso-opciones" className="vc-nuevo__linea" aria-current={paso === 1 ? 'step' : undefined}>{paso > 1 && <Check aria-hidden="true"/>}Opciones</h2>
          <div className="vc-dos-columnas">
            <label className="vc-campo"><span className="vc-campo__etiqueta">Título</span><input className="vc-campo__entrada" value={titulo} maxLength={200} placeholder="Un título para tu video" onChange={e => setTitulo(e.target.value)}/></label>
            <label className={`vc-campo${nombre && !nombreBien ? ' vc-campo--error' : ''}`}>
              <span className="vc-campo__etiqueta">Nombre del proyecto</span>
              <input className="vc-campo__entrada" required value={nombre} maxLength={60} placeholder="mi-primer-video" onChange={e => setNombre(e.target.value)} aria-invalid={Boolean(nombre) && !nombreBien}/>
              {nombre && !nombreBien ? <span className="vc-campo__error">Usa minúsculas, números y guiones. Por ejemplo: {nombreValido(nombre)}</span> : <span className="vc-campo__ayuda">Minúsculas, números y guiones; 60 caracteres como máximo.</span>}
            </label>
          </div>
          <OpcionesRender calidad={calidad} cambiar={setCalidad} orientacion={orientacion} cambiarOrientacion={setOrientacion}
            fondo={fondoVideo} cambiarFondo={setFondoVideo} tieneReferencia={Boolean(referencia)} deshabilitado={ocupado}/>
          <div className={`vc-campo${duracionValida ? '' : ' vc-campo--error'}`}>
            <label className="vc-campo__etiqueta" htmlFor="duracion-objetivo">Duración fija del video (minutos, opcional)</label>
            <input id="duracion-objetivo" className="vc-campo__entrada" type="number" min={1} max={120} step="any" placeholder="Libre" value={duracionObjetivo} disabled={ocupado} onChange={e => { setDuracionObjetivo(e.target.value); setEntradaDuracionInvalida(e.target.validity.badInput); }} aria-invalid={!duracionValida} aria-describedby="duracion-objetivo-ayuda"/>
            <span id="duracion-objetivo-ayuda" className={duracionValida ? 'vc-campo__ayuda' : 'vc-campo__error'}>{duracionValida ? 'FilmCode abrevia el guion y comprueba la duración al exportar. Si no cabe sin cortar frases o forzar el ritmo, te pedirá revisar el guion. Déjalo vacío para duración libre.' : 'Escribe una duración de 1 a 120 minutos o deja el campo vacío.'}</span>
          </div>
          <div className="vc-campo">
            <span className="vc-campo__etiqueta">Voz</span>
            <div><Selector etiqueta="Voz" valor={voz} cambiar={setVoz} ancho="320px" opciones={opcionesVoz(ajustes.data, voces.data)}/></div>
            <span className="vc-campo__ayuda">{necesitaVoiceStudio ? 'Cada frase nueva tarda unas 10 veces lo que dura; lo que ya está en caché no se repite.' : proveedor === 'edge' ? 'Sale en minutos, pero necesita internet.' : 'Sin narración: sirve para revisar la imagen.'}</span>
          </div>
          <div className="vc-dos-columnas">
            <div className={`vc-campo${velocidadVozValida ? '' : ' vc-campo--error'}`}>
              <label className="vc-campo__etiqueta" htmlFor="velocidad-voz">Velocidad de la voz</label>
              <div className="vc-velocidad__control">
                <input id="velocidad-voz" className="vc-campo__entrada" type="number" min={0.75} max={1.5} step={0.05} required value={velocidadVoz} disabled={ocupado} onChange={e => { setVelocidadVoz(e.target.value); setEntradaVelocidadVozInvalida(e.target.validity.badInput || e.target.validity.stepMismatch); }} aria-invalid={!velocidadVozValida} aria-describedby="velocidad-voz-ayuda"/>
                <output htmlFor="velocidad-voz">{velocidadVozValida ? `${numero(factorVoz, 2)}×` : '—'}</output>
                <button type="button" className="vc-boton" aria-label="Restablecer la velocidad de la voz a 1×" disabled={ocupado} onClick={() => { setVelocidadVoz('1'); setEntradaVelocidadVozInvalida(false); }}>Restablecer 1×</button>
              </div>
              <span id="velocidad-voz-ayuda" className={velocidadVozValida ? 'vc-campo__ayuda' : 'vc-campo__error'}>{velocidadVozValida ? 'Por defecto 1,15×. Elige 1× para conservar el ritmo original de la voz.' : 'Usa un valor entre 0,75 y 1,5 en pasos de 0,05.'}</span>
            </div>
            <div className={`vc-campo${velocidadAnimacionesValida ? '' : ' vc-campo--error'}`}>
              <label className="vc-campo__etiqueta" htmlFor="velocidad-animaciones">Velocidad de las animaciones</label>
              <div className="vc-velocidad__control">
                <input id="velocidad-animaciones" className="vc-campo__entrada" type="number" min={0.5} max={2} step={0.05} required value={velocidadAnimaciones} disabled={ocupado} onChange={e => { setVelocidadAnimaciones(e.target.value); setEntradaVelocidadAnimacionesInvalida(e.target.validity.badInput || e.target.validity.stepMismatch); }} aria-invalid={!velocidadAnimacionesValida} aria-describedby="velocidad-animaciones-ayuda"/>
                <output htmlFor="velocidad-animaciones">{velocidadAnimacionesValida ? `${numero(factorAnimaciones, 2)}×` : '—'}</output>
                <button type="button" className="vc-boton" aria-label="Restablecer la velocidad de las animaciones a 1×" disabled={ocupado} onClick={() => { setVelocidadAnimaciones('1'); setEntradaVelocidadAnimacionesInvalida(false); }}>Restablecer 1×</button>
              </div>
              <span id="velocidad-animaciones-ayuda" className={velocidadAnimacionesValida ? 'vc-campo__ayuda' : 'vc-campo__error'}>{velocidadAnimacionesValida ? 'Las rápidas conservan las pausas de la narración; las lentas pueden alargar el video.' : 'Usa un valor entre 0,5 y 2 en pasos de 0,05.'}</span>
            </div>
          </div>
          <label className="vc-campo">
            <span className="vc-campo__etiqueta"><input type="checkbox" checked={vozFluida} disabled={ocupado} onChange={e => setVozFluida(e.target.checked)}/> Narración continua</span>
            <span className="vc-campo__ayuda">Reduce pausas entre bloques sin regenerar tu voz</span>
          </label>
          {referencia ? <p className="vc-nota">Con una referencia visual, las demostraciones se preparan con los pasos de la fuente sin ejecutar sus comandos.</p> : <Interruptor marcado={capturar} cambiar={setCapturar} ayuda={enDocker ? 'Si lo activas, los comandos permitidos se ejecutan dentro del contenedor.' : 'Actívalo solo si quieres ejecutar comandos de comprobación permitidos, como docker version.'}>Ejecutar comandos de verificación reales</Interruptor>}
          <div className="vc-campo">
            <span className="vc-campo__etiqueta">Prioridad</span>
            <div><Selector etiqueta="Prioridad" valor={prioridad ? 'baja' : 'alta'} cambiar={valor => setPrioridad(valor === 'baja')} deshabilitado={ocupado || !prioridadDinamica} opciones={[{ valor: 'alta', texto: 'Alta' }, { valor: 'baja', texto: 'Baja' }]}/></div>
            <span className="vc-campo__ayuda">{prioridadDinamica ? AYUDA_PRIORIDAD : enDocker ? 'Docker usa los límites de CPU y memoria definidos en Compose. Este selector no cambia esos límites ni los procesos de Ollama o VoiceStudio del equipo anfitrión.' : 'El cambio de prioridad durante un trabajo solo está disponible en Windows. En este sistema no se ajustan los procesos de Ollama ni VoiceStudio.'}</span>
          </div>
          <details className="vc-plegable">
            <summary><ChevronRight aria-hidden="true"/>Avanzado: modelo</summary>
            <div className="vc-dos-columnas">
              <div className="vc-campo"><span className="vc-campo__etiqueta">Modelo de Ollama</span><Selector etiqueta="Modelo de Ollama" valor={modelo} cambiar={setModelo} opciones={(salud.data?.ollama.modelos ?? []).map(m => ({ valor: `ollama:${m}`, texto: m }))}/></div>
            </div>
          </details>
        </section>
      </div>
      <aside className="vc-nuevo__revision" aria-labelledby="paso-revision">
        <h2 id="paso-revision" className="vc-nuevo__linea" aria-current={paso === 2 ? 'step' : undefined}>Revisión</h2>
        <ul className="grid gap-3 m-0 p-0 list-none">
          <li className="flex justify-between gap-4"><span>Fuente</span><span className={`vc-insignia vc-insignia--${fuenteLista ? 'verde' : 'gris'}`}>{fuenteLista ? 'lista' : 'pendiente'}</span></li>
          <li className="flex justify-between gap-4"><span>Ollama</span><span className={`vc-insignia vc-insignia--${salud.data?.ollama.listo && modeloInstalado ? 'verde' : 'gris'}`}>{salud.data?.ollama.listo ? (modeloInstalado ? 'listo' : 'sin el modelo') : 'apagado'}</span></li>
          {necesitaVoiceStudio && <li className="flex justify-between gap-4"><span>VoiceStudio</span><span className={`vc-insignia vc-insignia--${salud.data?.voicestudio.listo ? 'verde' : 'gris'}`}>{salud.data?.voicestudio.listo ? 'listo' : 'apagado'}</span></li>}
          <li className="flex justify-between gap-4"><span>ffmpeg</span><span className={`vc-insignia vc-insignia--${salud.data?.ffmpeg ? 'verde' : 'gris'}`}>{salud.data?.ffmpeg ? 'listo' : 'no está'}</span></li>
        </ul>
        {impedimento && <Mensaje tono="aviso" accion={<button type="button" className="vc-boton vc-boton--chico" onClick={() => void refrescarSalud(cliente).catch((e: Error) => avisar(e.message, true))}>Reintentar</button>}>{impedimento}</Mensaje>}
        <p className="vc-nota">La fuente y la referencia adjunta se copian a la carpeta del proyecto. Los originales no se modifican.</p>
        <dl className="vc-nuevo__configuracion">
          <div><dt>Video</dt><dd>{describirCalidad(calidad).nombre}</dd></div>
          <div><dt>Voz</dt><dd>{nombreVoz}</dd></div>
          <div><dt>Ritmo de voz</dt><dd>{velocidadVozValida ? `${numero(factorVoz, 2)}×` : 'Revisa la velocidad'}</dd></div>
          <div><dt>Animaciones</dt><dd>{velocidadAnimacionesValida ? `${numero(factorAnimaciones, 2)}×` : 'Revisa la velocidad'}</dd></div>
          <div><dt>Narración continua</dt><dd>{vozFluida ? 'Activada' : 'Desactivada'}</dd></div>
          <div><dt>Orientación</dt><dd>{orientacion === 'vertical' ? 'Vertical · 9:16' : 'Horizontal · 16:9'}</dd></div>
          <div><dt>Fondo</dt><dd>{nombreFondoVideo(fondoVideo, Boolean(referencia))}</dd></div>
          <div><dt>Duración de exportación</dt><dd>{duracionValida ? minutosObjetivo == null ? 'Libre' : duracion(minutosObjetivo * 60) : 'Revisa los minutos'}</dd></div>
        </dl>
        <button className="vc-boton vc-boton--principal vc-boton--grande w-full" type="submit" disabled={!fuenteLista || !nombreBien || !duracionValida || !velocidadesValidas || Boolean(impedimento) || ocupado}>{ocupado ? 'Preparando…' : creado ? 'Reintentar el inicio' : 'Hacer video'}</button>
        <p className="vc-nota">El análisis y el guion pueden tardar. Podrás seguir el progreso y cancelar.</p>
      </aside>
    </div>
  </form>;
}
