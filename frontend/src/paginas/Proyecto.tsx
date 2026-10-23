import { lazy, Suspense } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { baseProyecto, enviar, useDatos } from '../api';
import type { Detalle } from '../tipos';
import { fechaCorta } from '../logica';
import { Cargando, ErrorVista, navegarPestanas, Pasos, avisar } from '../componentes/Comun';
import type { Paso } from '../componentes/Comun';
import { useConfirmar } from '../componentes/Controles';
import { Resumen } from './Resumen';
import { VideoVista } from './VideoVista';
import { CodigoVista, ComandosVista, ModeloVista } from './Revision';

const GuionEditor = lazy(() => import('./GuionEditor').then(m => ({ default: m.GuionEditor })));
const TIPOS: Record<string, string> = { codigo: 'Código', documento: 'Guía', carpeta: 'Carpeta' };

export function pasosDe(p: Detalle): { pasos: Paso[]; actual: number } {
  const videoAlDia = p.videos.some(v => !v.desactualizado);
  const pasos: Paso[] = [{ titulo: 'Fuente', hecho: true }, { titulo: 'Guion', hecho: p.tiene_guion }, { titulo: 'Video', hecho: videoAlDia }];
  // Si algo corre o quedó cortado, el paso actual es el de ese trabajo, no el primero pendiente.
  const enTrabajo = p.situacion !== 'listo' ? (/guion/.test(p.etapa) || p.trabajo?.tipo === 'guion' ? 1 : p.etapa.startsWith('renderizando') || p.trabajo?.tipo === 'render' ? 2 : -1) : -1;
  const actual = enTrabajo >= 0 ? enTrabajo : pasos.findIndex(paso => !paso.hecho);
  if (actual >= 0) {
    const aviso = p.situacion === 'interrumpido' ? { texto: 'interrumpido', color: 'amarillo' as const }
      : p.situacion === 'error' ? { texto: 'error', color: 'rojo' as const }
      : p.situacion.startsWith('en_curso') ? { texto: 'en curso', color: 'amarillo' as const }
      : actual === 2 && p.videos.length > 0 && !videoAlDia ? { texto: 'desactualizado', color: 'amarillo' as const } : undefined;
    pasos[actual] = { ...pasos[actual], aviso };
  }
  return { pasos, actual };
}

export function ProyectoVista() {
  const { nombre = '' } = useParams();
  const consulta = useDatos<Detalle>(baseProyecto(nombre), 2000);
  const [parametros, setParametros] = useSearchParams();
  const vista = parametros.get('vista') ?? 'resumen';
  const navegar = useNavigate(), cliente = useQueryClient(), confirmar = useConfirmar();
  const proyecto = consulta.data;
  async function archivar() {
    if (!await confirmar({ titulo: '¿Archivar el proyecto?', texto: <p>Se mueve a <code>videos/_archivo</code>. No se borra nada: puedes devolverlo a su lugar cuando quieras.</p>, aceptar: 'Archivar' })) return;
    try { await enviar(`${baseProyecto(nombre)}/archivar`, {}); await cliente.invalidateQueries(); avisar(`${nombre} quedó en videos/_archivo.`); navegar('/proyectos'); }
    catch (e) { avisar((e as Error).message, true); }
  }
  if (consulta.isPending) return <div className="vc-pagina"><Cargando/></div>;
  if (!proyecto) return <div className="vc-pagina"><ErrorVista error={consulta.error} reintentar={() => void consulta.refetch()}/></div>;
  const ocupado = proyecto.situacion.startsWith('en_curso');
  const { pasos, actual } = pasosDe(proyecto);
  const pestanas = [['resumen', 'Resumen'], ['guion', 'Guion'], ['video', 'Video'], ...(proyecto.tipo === 'documento' ? [['comandos', 'Comandos reales']] : []), ['modelo', 'Modelo'], ['codigo', 'Código']];
  const ir = (id: string) => setParametros(id === 'resumen' ? {} : { vista: id });
  return <div className="vc-pagina">
    <Link className="vc-volver" to="/proyectos"><ArrowLeft aria-hidden="true"/>Proyectos</Link>
    <div className="vc-cabeza">
      <div className="min-w-0">
        <h1 className="titulo vc-titulo-largo" title={proyecto.titulo}>{proyecto.titulo}</h1>
        <p className="vc-cabeza__meta">
          <span>{TIPOS[proyecto.tipo] ?? proyecto.tipo}</span>
          <span>{proyecto.nombre}</span>
          <span>actualizado {fechaCorta(proyecto.actualizado)}</span>
        </p>
      </div>
      <button className="vc-boton" disabled={ocupado} onClick={() => void archivar()}>Archivar</button>
    </div>
    <div className="vc-proyecto__pasos"><Pasos pasos={pasos} actual={actual}/></div>
    <div className="vc-pestanas vc-proyecto__pestanas" role="tablist" aria-label="Secciones del proyecto" onKeyDown={navegarPestanas}>
      {pestanas.map(([id, texto]) => <button key={id} role="tab" className="vc-pestana" aria-selected={vista === id} tabIndex={vista === id ? 0 : -1} onClick={() => ir(id)}>{texto}</button>)}
    </div>
    <div role="tabpanel" aria-label={pestanas.find(([id]) => id === vista)?.[1]}>
      {vista === 'resumen' ? <Resumen proyecto={proyecto} ir={ir}/>
        : vista === 'guion' ? <Suspense fallback={<Cargando/>}><GuionEditor key={nombre} nombre={nombre} ocupado={ocupado}/></Suspense>
        : vista === 'video' ? <VideoVista proyecto={proyecto}/>
        : vista === 'comandos' ? <ComandosVista nombre={nombre}/>
        : vista === 'modelo' ? <ModeloVista nombre={nombre}/>
        : <CodigoVista nombre={nombre}/>}
    </div>
  </div>;
}
