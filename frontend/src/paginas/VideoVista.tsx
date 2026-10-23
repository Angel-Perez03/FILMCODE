import { useEffect, useRef, useState } from 'react';
import type { CSSProperties, KeyboardEvent, MouseEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Download, Pause, Play } from 'lucide-react';
import { baseProyecto, enviar, useDatos } from '../api';
import type { Narrado, Proyecto, Trabajo } from '../tipos';
import { configRenderInicial, describirCalidad, duracion, fechaCorta, numero, tiempoLegible } from '../logica';
import { avisar, Cargando, ErrorVista, Insignia, Mensaje, navegarPestanas, Vacio } from '../componentes/Comun';
import { Icono } from '../componentes/Icono';

const nombreCapitulo = (c: Narrado['capitulos'][number]) => `Escena ${c.escena} · ${c.tipo}${c.titulo && !/^Escena \d+$/.test(c.titulo) ? ` · ${c.titulo}` : ''}`;

export function VideoVista({ proyecto }: {proyecto: Proyecto}) {
  const versiones = [...proyecto.videos].sort((a, b) => b.fecha.localeCompare(a.fecha));
  const preferido = versiones.find(v => !v.desactualizado) ?? versiones[0];
  const [seleccion, setSeleccion] = useState<{proyecto: string; calidad: string} | null>(null);
  const calidad = seleccion?.proyecto === proyecto.nombre && versiones.some(v => v.calidad === seleccion.calidad)
    ? seleccion.calidad : preferido?.calidad ?? configRenderInicial(proyecto.preferencias?.calidad);
  const [tiempo, setTiempo] = useState(0), [total, setTotal] = useState(0), [reproduciendo, setReproduciendo] = useState(false);
  const [panel, setPanel] = useState<'transcripcion' | 'capitulos'>('transcripcion');
  const [seguir, setSeguir] = useState(true), [error, setError] = useState<Error | null>(null), [generando, setGenerando] = useState(false);
  const reproductor = useRef<HTMLVideoElement>(null), lista = useRef<HTMLOListElement>(null);
  const base = baseProyecto(proyecto.nombre), video = proyecto.videos.find(v => v.calidad === calidad);
  const narrado = useDatos<Narrado>(`${base}/narrado/${calidad}`, undefined, Boolean(video));
  const hojas = useDatos<string[]>(`${base}/hojas/${calidad}`, undefined, Boolean(video));
  const cliente = useQueryClient();
  const bloques = narrado.data?.bloques ?? [], capitulos = narrado.data?.capitulos ?? [];
  const activo = bloques.findIndex(b => tiempo >= b.inicio && tiempo < b.inicio + b.duracion);
  const capitulo = [...capitulos].reverse().find(c => tiempo >= c.inicio);
  const largo = total || video?.duracion || narrado.data?.duracion_total || 1;

  useEffect(() => { setTiempo(0); setTotal(0); setReproduciendo(false); setError(null); }, [proyecto.nombre, calidad, video?.fecha]);
  useEffect(() => {
    const contenedor = lista.current, elemento = contenedor?.querySelector<HTMLElement>('[aria-current="true"]');
    if (seguir && contenedor && elemento) contenedor.scrollTo({ top: elemento.offsetTop - contenedor.clientHeight / 3 });
  }, [activo, seguir, panel]);
  function saltar(segundos: number) {
    if (!reproductor.current) return;
    reproductor.current.currentTime = Math.max(0, Math.min(segundos, largo));
    setTiempo(reproductor.current.currentTime); setSeguir(true);
  }
  function alternar() { const v = reproductor.current; if (!v) return; if (v.paused) void v.play(); else v.pause(); }
  function clicLinea(e: MouseEvent<HTMLDivElement>) { const caja = e.currentTarget.getBoundingClientRect(); saltar((e.clientX - caja.left) / caja.width * largo); }
  function teclaLinea(e: KeyboardEvent<HTMLDivElement>) {
    const pasos: Record<string, number> = { ArrowRight: 5, ArrowLeft: -5, PageUp: 30, PageDown: -30 };
    if (e.key in pasos) { e.preventDefault(); saltar(tiempo + pasos[e.key]); }
    else if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); saltar(e.key === 'Home' ? 0 : largo); }
  }
  async function generar() {
    setGenerando(true);
    try { await enviar<Trabajo>(`${base}/trabajos`, { tipo: 'fotogramas', calidad }); await cliente.invalidateQueries(); avisar('Generando las hojas de miniaturas. El progreso sale en Resumen.'); }
    catch (e) { setError(e as Error); } finally { setGenerando(false); }
  }
  if (!proyecto.videos.length) return <Vacio titulo="Todavía no hay un video"><p>Cuando termine un render, aquí lo verás con subtítulos, capítulos y la transcripción.</p></Vacio>;

  return <div className="grid gap-8">
    <div className="vc-pestanas" role="tablist" aria-label="Versiones del video" onKeyDown={navegarPestanas}>
      {versiones.map((v, i) => {
        const etiqueta = describirCalidad(v.calidad).nombre;
        const repetida = versiones.some(otra => otra.calidad !== v.calidad && describirCalidad(otra.calidad).nombre === etiqueta);
        return <button key={v.calidad} role="tab" className="vc-pestana" aria-label={`${etiqueta} · versión ${versiones.length - i} · ${fechaCorta(v.fecha)}`} aria-selected={calidad === v.calidad} tabIndex={calidad === v.calidad ? 0 : -1} onClick={() => setSeleccion({ proyecto: proyecto.nombre, calidad: v.calidad })}>
          {etiqueta}{repetida && <span className="pequeno"> · {fechaCorta(v.fecha)} · v{versiones.length - i}</span>}{v.desactualizado && <Insignia texto="desactualizado" color="amarillo"/>}
        </button>;
      })}
    </div>
    {video?.desactualizado && <Mensaje tono="aviso">El guion cambió después de este render: el video y sus capítulos pueden no coincidir con la versión actual.</Mensaje>}
    <div className="vc-video">
      <div className="vc-reproductor">
        <video key={`${proyecto.nombre}-${calidad}-${video?.fecha}`} ref={reproductor} className="vc-marco" preload="metadata" src={`/api${base}/video/${calidad}`} poster={proyecto.miniatura}
          onClick={alternar} onTimeUpdate={e => setTiempo(e.currentTarget.currentTime)} onLoadedMetadata={e => setTotal(e.currentTarget.duration)}
          onPlay={() => { setReproduciendo(true); setSeguir(true); }} onPause={() => setReproduciendo(false)}
          onError={() => setError(new Error('No se pudo reproducir el video. Comprueba que el archivo siga en salida/.'))}>
          <track kind="subtitles" src={`/api${base}/subtitulos/${calidad}.vtt`} srcLang="es" label="Español"/>
        </video>
        <p className="vc-reproductor__subtitulo entrada">{activo >= 0 ? bloques[activo].texto : ''}</p>
        <div className="vc-tiempo" role="slider" tabIndex={0} aria-label="Tiempo del video" aria-valuemin={0} aria-valuemax={Math.round(largo)} aria-valuenow={Math.round(tiempo)} aria-valuetext={`${duracion(tiempo)} de ${duracion(largo)}`} onClick={clicLinea} onKeyDown={teclaLinea}>
          <span className="vc-tiempo__visto" style={{ '--valor': tiempo / largo } as CSSProperties}/>
          {capitulos.slice(1).map(c => <span key={c.escena} className="vc-tiempo__capitulo" style={{ left: `${c.inicio / largo * 100}%` }}/>)}
        </div>
        <div className="vc-reproductor__controles">
          <button className="vc-boton vc-boton--icono" onClick={alternar} aria-label={reproduciendo ? 'Pausar' : 'Reproducir'}>{reproduciendo ? <Pause aria-hidden="true"/> : <Play aria-hidden="true"/>}</button>
          <span className="vc-cifras pequeno text-texto-suave">{duracion(tiempo)} / {duracion(largo)}</span>
          <span className="vc-reproductor__capitulo pequeno">{capitulo ? nombreCapitulo(capitulo) : ''}</span>
          <a className="vc-boton" download={`${proyecto.nombre}-${calidad}.mp4`} href={`/api${base}/video/${calidad}?descargar=true`}><Download aria-hidden="true"/>Descargar</a>
        </div>
        {video && <dl className="vc-video__datos">
          <div><dt>Duración</dt><dd>{duracion(video.duracion)}</dd></div>
          <div><dt>Archivo</dt><dd>{numero(video.megas)} MB</dd></div>
          <div><dt>Render</dt><dd>{video.segundos_render ? tiempoLegible(video.segundos_render) : '—'}</dd></div>
          <div><dt>Creado</dt><dd>{fechaCorta(video.fecha)}</dd></div>
        </dl>}
        <ErrorVista error={error}/>
      </div>
      <aside className="vc-video__lateral" aria-label="Narración">
        <div className="vc-pestanas" role="tablist" aria-label="Narración" onKeyDown={navegarPestanas}>
          <button role="tab" className="vc-pestana" aria-selected={panel === 'transcripcion'} tabIndex={panel === 'transcripcion' ? 0 : -1} onClick={() => setPanel('transcripcion')}>Transcripción</button>
          <button role="tab" className="vc-pestana" aria-selected={panel === 'capitulos'} tabIndex={panel === 'capitulos' ? 0 : -1} onClick={() => setPanel('capitulos')}>Capítulos {capitulos.length > 0 && <span className="vc-cifras pequeno text-gris">{capitulos.length}</span>}</button>
        </div>
        {narrado.isPending ? <div className="p-4"><Cargando/></div> : panel === 'transcripcion' ? <ol ref={lista} className="vc-transcripcion" aria-label="Transcripción" onWheel={() => setSeguir(false)} onTouchMove={() => setSeguir(false)}>
          {bloques.map((b, i) => <li key={`${i}-${b.inicio}`}>
            <button className="vc-transcripcion__linea" aria-current={activo === i ? 'true' : undefined} onClick={() => saltar(b.inicio)}><time>{duracion(b.inicio)}</time><span>{b.texto}</span></button>
          </li>)}
        </ol> : <ol ref={lista} className="vc-capitulos" aria-label="Capítulos">
          {capitulos.map(c => <li key={c.escena}>
            <button className="vc-capitulo" aria-current={capitulo?.escena === c.escena ? 'true' : undefined} onClick={() => saltar(c.inicio)}><Icono nombre={c.tipo} size={18}/><span>{nombreCapitulo(c)}</span><time>{duracion(c.inicio)}</time></button>
          </li>)}
        </ol>}
        <ErrorVista error={narrado.error}/>
      </aside>
    </div>
    <section className="vc-seccion" aria-labelledby="hojas-titulo">
      <div className="vc-cabeza" style={{ marginBottom: 24 }}>
        <div>
          <h2 id="hojas-titulo" className="vc-subtitulo" style={{ margin: 0 }}>Hojas de revisión</h2>
          <p className="vc-nota">Una imagen cada 5 segundos. Pulsa una para saltar a ese momento.</p>
        </div>
        <button className="vc-boton" disabled={generando || proyecto.situacion.startsWith('en_curso')} onClick={() => void generar()}>{generando ? 'Iniciando…' : 'Generar hojas'}</button>
      </div>
      <ErrorVista error={hojas.error}/>
      {hojas.data?.length ? <div className="vc-hojas">
        {hojas.data.map((archivo, k) => <figure key={archivo} className="vc-hoja">
          <img src={`/api${base}/hojas/${calidad}/${encodeURIComponent(archivo)}`} alt={`Hoja ${k + 1}: nueve fotogramas del video`} loading="lazy"/>
          <div className="vc-hoja__saltos">{Array.from({ length: 9 }, (_, j) => { const segundo = (k * 9 + j) * 5; return <button key={j} aria-label={`Ir a ${duracion(segundo)}`} onClick={() => { saltar(segundo); reproductor.current?.scrollIntoView({ block: 'center' }); }}><span>{duracion(segundo)}</span></button>; })}</div>
        </figure>)}
      </div> : hojas.data && <p className="vc-nota">Este render todavía no tiene hojas de miniaturas.</p>}
    </section>
  </div>;
}
