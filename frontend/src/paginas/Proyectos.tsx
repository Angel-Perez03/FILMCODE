import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useDatos } from '../api';
import type { Proyecto } from '../tipos';
import { describirCalidad, duracion, estadoProyecto, fechaCorta, numero } from '../logica';
import { Cargando, ErrorVista, Insignia, Progreso, Vacio } from '../componentes/Comun';
import { capturarFlip } from '../movimiento/flip';

const TIPOS: Record<string, string> = { codigo: 'Código', documento: 'Guía', carpeta: 'Carpeta' };
const ultimo = (p: Proyecto) => {
  const videos = [...p.videos].sort((a, b) => b.fecha.localeCompare(a.fecha));
  return videos.find(v => !v.desactualizado) ?? videos[0];
};

export function Proyectos() {
  const consulta = useDatos<Proyecto[]>('/proyectos', 2000);
  const proyectos = [...(consulta.data ?? [])].sort((a, b) => (b.actualizado ?? '').localeCompare(a.actualizado ?? ''));
  const [elegido, setElegido] = useState('');
  const activo = proyectos.find(p => p.nombre === elegido) ?? proyectos[0];
  const video = activo && ultimo(activo);
  return <div className="vc-pagina">
    <div className="vc-cabeza">
      <div>
        <h1 className="titulo">Proyectos</h1>
        {consulta.data && <p className="vc-cabeza__meta"><span>{proyectos.length} {proyectos.length === 1 ? 'proyecto' : 'proyectos'}</span><span>{proyectos.filter(p => p.videos.length).length} con video</span></p>}
      </div>
      <Link className="vc-boton vc-boton--principal" to="/nuevo">Nuevo video</Link>
    </div>
    <ErrorVista error={consulta.error} reintentar={() => void consulta.refetch()}/>
    {consulta.isPending ? <Cargando/> : proyectos.length === 0 ? <Vacio titulo="Todavía no hay proyectos">
      <p>Hay tres formas de empezar: arrastra un archivo o una carpeta, escribe la ruta de tu código o pega una guía en Markdown.</p>
      <Link className="vc-boton vc-boton--principal" to="/nuevo">Elegir código</Link>
    </Vacio> : <div className="vc-indice">
      <ol className="vc-indice__filas">
        {proyectos.map(p => {
          const v = ultimo(p), estado = estadoProyecto(p), corriendo = p.situacion.startsWith('en_curso');
          return <li key={p.nombre} className="vc-fila">
            <Link to={`/proyectos/${p.nombre}`} className="vc-fila__enlace" aria-current={activo?.nombre === p.nombre ? 'true' : undefined} onClick={() => capturarFlip(`miniatura-${p.nombre}`)}
              onPointerEnter={() => setElegido(p.nombre)} onFocus={() => setElegido(p.nombre)}>
              <p className="vc-fila__titulo entrada">{p.titulo}</p>
              <span className="vc-fila__estado"><Insignia texto={estado.texto} color={estado.color}/></span>
              <span className="vc-fila__meta">
                <span>{TIPOS[p.tipo] ?? p.tipo}</span>
                <span>{p.etapa.startsWith('renderizando ') ? `Renderizando ${describirCalidad(p.etapa.slice(13)).nombre}` : describirCalidad(p.etapa).nombre}</span>
                {v && <span className="vc-cifras">{describirCalidad(v.calidad).nombre} · {duracion(v.duracion)}</span>}
                <span className="vc-cifras">{fechaCorta(p.actualizado)}</span>
              </span>
              {corriendo && <span className="vc-fila__progreso"><Progreso valor={p.progreso || null} mensaje={p.mensaje || p.etapa} cifras={p.progreso ? `${numero(p.progreso)} %` : undefined}/></span>}
              {v && <img className="vc-fila__miniatura vc-marco" src={p.miniatura} alt="" loading="lazy" data-flip-id={`miniatura-${p.nombre}`}/>}
            </Link>
          </li>;
        })}
      </ol>
      {activo && <figure className="vc-indice__vista" aria-live="polite">
        {video ? <img className="vc-marco" src={activo.miniatura} alt={`Fotograma de ${activo.titulo}`} data-flip-id={`miniatura-${activo.nombre}`}/> : <div className="vc-marco vc-marco--vacio">Sin video todavía</div>}
        <figcaption>{video ? `${describirCalidad(video.calidad).nombre} · ${duracion(video.duracion)} · ${numero(video.megas)} MB${video.desactualizado ? ' · desactualizado: el guion cambió después del render' : ''}` : activo.mensaje || 'Todavía no se renderizó ningún video.'}</figcaption>
      </figure>}
    </div>}
  </div>;
}
