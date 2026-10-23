import { Link } from 'react-router-dom';
import { ArrowRight, FileCode2, Plus } from 'lucide-react';
import { useDatos } from '../api';
import type { Proyecto, Salud, Trabajo } from '../tipos';
import { duracion, estadoProyecto, fechaCorta } from '../logica';
import { Cargando, ErrorVista, Insignia, Progreso } from '../componentes/Comun';

const PASOS = [
  ['Fuente', 'Un archivo, una carpeta o tu guía.'],
  ['Guion', 'La explicación, las escenas y la duración.'],
  ['Voces', 'Se prepara la narración y se conserva en caché.'],
  ['Animaciones', 'Manim convierte el guion en escenas.'],
  ['Video', 'El archivo final, con subtítulos y capítulos.'],
];

export function Inicio() {
  const consulta = useDatos<Proyecto[]>('/proyectos', 10000);
  const trabajos = useDatos<Trabajo[]>('/trabajos');
  const salud = useDatos<Salud>('/salud', 10000);
  const proyectos = [...(consulta.data ?? [])].sort((a, b) => b.actualizado.localeCompare(a.actualizado));
  const trabajo = trabajos.data?.find(t => t.estado === 'corriendo');
  const activo = proyectos.find(p => p.nombre === trabajo?.proyecto) ?? proyectos.find(p => p.situacion.startsWith('en_curso'));
  const nombreActivo = trabajo?.proyecto ?? activo?.nombre;

  return <div className="vc-inicio">
    <section className="vc-inicio__apertura" aria-labelledby="inicio-titulo">
      <div className="vc-inicio__presentacion">
        <h1 id="inicio-titulo">Tu próximo video<br/>empieza aquí.</h1>
        <p>Convierte tu código o una guía en un video narrado. Define la duración, revisa el guion y sigue cada fase desde el mismo lugar.</p>
        <div className="vc-inicio__acciones">
          <Link className="vc-boton vc-boton--principal vc-boton--grande" to="/nuevo"><Plus aria-hidden="true"/>Crear video</Link>
          <Link className="vc-inicio__enlace" to="/proyectos">Abrir mis proyectos<ArrowRight aria-hidden="true"/></Link>
        </div>
        <p className="vc-inicio__nota">Cada proyecto conserva su guion, su progreso y los archivos que ya generó.</p>
      </div>
      <aside className="vc-inicio__flujo" aria-labelledby="flujo-titulo">
        <h2 id="flujo-titulo">De la fuente al video</h2>
        <ol>{PASOS.map(([titulo, detalle]) => <li key={titulo}><span className="vc-inicio__punto" aria-hidden="true"/><div><strong>{titulo}</strong><p>{detalle}</p></div></li>)}</ol>
      </aside>
    </section>

    {nombreActivo && <section className="vc-inicio__activo" aria-labelledby="trabajo-inicio-titulo" data-ui>
      <div>
        <Insignia texto="Trabajo en curso" color="amarillo"/>
        <h2 id="trabajo-inicio-titulo">{activo?.titulo ?? nombreActivo}</h2>
        <Progreso valor={(trabajo ? trabajo.progreso : activo?.progreso) || null} mensaje={trabajo?.mensaje || activo?.mensaje || 'Preparando el trabajo'}/>
      </div>
      <Link className="vc-boton vc-boton--principal" to={`/proyectos/${encodeURIComponent(nombreActivo)}`}>Seguir el progreso<ArrowRight aria-hidden="true"/></Link>
    </section>}

    <section className="vc-inicio__mesa" aria-labelledby="proyectos-inicio-titulo">
      <div className="vc-inicio__proyectos" data-ui>
        <div className="vc-inicio__cabecera"><h2 id="proyectos-inicio-titulo">Retoma donde quedaste</h2><Link className="vc-inicio__enlace" to="/proyectos">Ver todos<ArrowRight aria-hidden="true"/></Link></div>
        <ErrorVista error={consulta.error} reintentar={() => void consulta.refetch()}/>
        {consulta.isPending ? <Cargando/> : proyectos.length ? <ol className="vc-inicio__lista">
          {proyectos.slice(0, 4).map(p => {
            const estado = estadoProyecto(p);
            const video = [...p.videos].sort((a, b) => b.fecha.localeCompare(a.fecha))[0];
            return <li key={p.nombre}><Link to={`/proyectos/${encodeURIComponent(p.nombre)}`}>
              {p.miniatura && video ? <img src={p.miniatura} alt="" width={112} height={63} loading="lazy"/> : <span className="vc-inicio__sin-video"><FileCode2 aria-hidden="true"/></span>}
              <span className="vc-inicio__proyecto"><strong>{p.titulo}</strong><span>{video ? `${duracion(video.duracion)} · ` : ''}{fechaCorta(p.actualizado)}</span></span>
              <Insignia texto={estado.texto} color={estado.color}/><ArrowRight className="vc-inicio__abrir" aria-hidden="true"/>
            </Link></li>;
          })}
        </ol> : !consulta.error && <div className="vc-inicio__vacio"><h3>Todo listo para tu primer proyecto</h3><p>Empieza con el material que quieres explicar. En el siguiente paso eliges la voz, la calidad y la duración objetivo.</p><Link className="vc-inicio__enlace" to="/nuevo">Crear mi primer video<ArrowRight aria-hidden="true"/></Link></div>}
      </div>
      <aside className="vc-inicio__equipo" aria-labelledby="equipo-inicio-titulo">
        <h2 id="equipo-inicio-titulo">Tu equipo</h2><p>Si es tu primera vez, revisa las instalaciones y los modelos que necesitas.</p>
        <Link className="vc-inicio__enlace" to="/ajustes#preparar-equipo">Preparar mi equipo<ArrowRight aria-hidden="true"/></Link>
        <dl>
          <div><dt>Guion · Ollama</dt><dd><Insignia texto={salud.error ? 'sin conexión' : salud.data ? salud.data.ollama.listo ? 'listo' : 'apagado' : 'consultando'} color={!salud.error && salud.data?.ollama.listo ? 'verde' : 'gris'}/></dd></div>
          <div><dt>Voz · VoiceStudio</dt><dd><Insignia texto={salud.error ? 'sin conexión' : salud.data ? salud.data.voicestudio.listo ? 'listo' : 'apagado' : 'consultando'} color={!salud.error && salud.data?.voicestudio.listo ? 'verde' : 'gris'}/></dd></div>
          <div><dt>Video · FFmpeg</dt><dd><Insignia texto={salud.error ? 'sin conexión' : salud.data ? salud.data.ffmpeg ? 'listo' : 'no disponible' : 'consultando'} color={!salud.error && salud.data?.ffmpeg ? 'verde' : 'gris'}/></dd></div>
        </dl>
        <Link className="vc-inicio__enlace" to="/ajustes">Abrir ajustes<ArrowRight aria-hidden="true"/></Link>
      </aside>
    </section>
  </div>;
}
