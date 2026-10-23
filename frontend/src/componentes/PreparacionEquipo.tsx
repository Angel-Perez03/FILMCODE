import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { peticion, useDatos } from '../api';
import { avisar, Cargando, ErrorVista, Insignia } from './Comun';
import './preparacion.css';

interface Requisito {
  id: string;
  nombre: string;
  estado: 'listo' | 'pendiente' | 'sin_confirmar' | 'opcional';
  necesario_para: string;
  detalle: string;
  accion: string;
  comando?: string;
  url?: string;
  tamano?: string;
}

interface Preparacion {
  modo: 'nativo' | 'docker';
  requisitos: Requisito[];
  notas: string[];
  capacidades?: { prioridad_dinamica?: boolean; rutas_anfitrion?: boolean; modo?: 'docker' | 'nativo' };
}

const ESTADOS = {
  listo: { texto: 'Listo', color: 'verde' },
  pendiente: { texto: 'Pendiente', color: 'amarillo' },
  sin_confirmar: { texto: 'Sin confirmar', color: 'gris' },
  opcional: { texto: 'Opcional', color: 'gris' },
} as const;

export function PreparacionEquipo() {
  const cliente = useQueryClient();
  const consulta = useDatos<Preparacion>('/preparacion');
  const [comprobando, setComprobando] = useState(false);
  const datos = consulta.data;
  const listos = datos?.requisitos.filter(r => r.estado === 'listo').length ?? 0;

  async function comprobar() {
    setComprobando(true);
    try {
      await cliente.cancelQueries({ queryKey: ['/preparacion'], exact: true });
      const resultado = await peticion<Preparacion>('/preparacion?forzar=true');
      cliente.setQueryData(['/preparacion'], resultado);
    } catch (error) {
      avisar((error as Error).message, true);
    } finally {
      setComprobando(false);
    }
  }

  return <section id="preparar-equipo" className="vc-preparacion" aria-labelledby="preparar-equipo-titulo">
    <div className="vc-preparacion__cabecera">
      <div>
        <h2 id="preparar-equipo-titulo" className="vc-subtitulo">Prepara tu equipo</h2>
        <p className="vc-nota">Consulta lo que necesitas para crear guiones, voces y videos. La comprobación solo lee el estado; el asistente de Windows permite preparar los componentes que tú autorices.</p>
      </div>
      <button className="vc-boton" type="button" disabled={consulta.isFetching || comprobando} onClick={() => void comprobar()}>{consulta.isFetching || comprobando ? 'Comprobando…' : 'Volver a comprobar'}</button>
    </div>
    <div className="vc-preparacion__instalador" aria-labelledby="instalador-windows-titulo">
      <div>
        <h3 id="instalador-windows-titulo">Asistente para Windows</h3>
        <p>Detecta qué falta en tu PC y te permite descargar Ollama, Gemma y VoiceStudio. Antes de cada descarga muestra el componente, su origen y su tamaño; tú decides si continuar.</p>
      </div>
      <div className="vc-preparacion__acciones">
        <a className="vc-boton vc-boton--principal" href="/instalador/instalador-windows.zip" download>Descargar asistente de Windows</a>
        <a className="vc-preparacion__enlace" href="/instalador/README.md" target="_blank" rel="noreferrer">Leer instrucciones<span className="vc-oculto"> (se abre en otra pestaña)</span></a>
      </div>
      <ol className="vc-preparacion__pasos">
        <li>Extrae el ZIP en una carpeta y abre <code>Instalar-FilmCode.cmd</code> con doble clic.</li>
        <li>Revisa lo detectado y confirma solo las instalaciones y descargas que quieras.</li>
        <li>Vuelve aquí y pulsa «Volver a comprobar» cuando hayas preparado los servicios.</li>
      </ol>
      <p className="vc-nota">Se ejecuta en Windows, también si usas FilmCode en Docker. No incluye voces ni grabaciones: cada persona configura su propio perfil en VoiceStudio. Descargar el ZIP no instala nada.</p>
    </div>
    <ErrorVista error={consulta.error} reintentar={() => void consulta.refetch()}/>
    {consulta.isPending && <Cargando/>}
    {datos && <>
      <div className="vc-preparacion__modo">
        <strong>{datos.modo === 'docker' ? 'Estás usando Docker' : 'Estás usando la instalación nativa'}</strong>
        <p>{datos.modo === 'docker'
          ? 'La imagen incluye Python, Manim y FFmpeg; Node compila la interfaz al construirla. Ollama y VoiceStudio se preparan aparte en el equipo anfitrión.'
          : 'La instalación nativa necesita Python dentro de .venv, las dependencias de Manim y FFmpeg. Node se usa para compilar la interfaz. Ollama y VoiceStudio se preparan aparte.'}</p>
        <p>Para la voz local necesitas CosyVoice 3, un perfil con tu audio de referencia y un modelo Whisper para sincronizar las palabras. Que VoiceStudio responda no confirma que esos modelos estén instalados o preparados.</p>
        {datos.capacidades?.prioridad_dinamica === false && <p>{datos.modo === 'docker' ? 'Los límites de CPU y memoria se definen en Compose. FilmCode no cambia los procesos de Ollama ni VoiceStudio del equipo anfitrión.' : 'El control dinámico de prioridad está disponible en la instalación nativa de Windows.'}</p>}
        {datos.capacidades?.rutas_anfitrion === false && <p>Las rutas de tu equipo no se ven directamente desde el contenedor. Sube los archivos desde la interfaz o monta una carpeta de entrada.</p>}
      </div>
      <p className="vc-nota vc-cifras">{listos} de {datos.requisitos.length} requisitos confirmados. «Sin confirmar» requiere una comprobación manual; «Opcional» depende de la voz o del flujo que elijas.</p>
      <ol className="vc-preparacion__lista">
        {datos.requisitos.map(requisito => <ElementoRequisito key={requisito.id} requisito={requisito}/>)}
      </ol>
      {datos.notas.length > 0 && <ul className="vc-preparacion__notas">{datos.notas.map(nota => <li key={nota}>{nota}</li>)}</ul>}
    </>}
  </section>;
}

function ElementoRequisito({ requisito }: { requisito: Requisito }) {
  const estado = ESTADOS[requisito.estado];
  const enlace = requisito.url && /^https?:\/\//i.test(requisito.url) ? requisito.url : undefined;

  async function copiar() {
    if (!requisito.comando) return;
    try {
      await navigator.clipboard.writeText(requisito.comando);
      avisar('Comando copiado. Revísalo y ejecútalo tú en una terminal.');
    } catch {
      avisar('No se pudo copiar. Selecciona el comando y cópialo manualmente.', true);
    }
  }

  return <li className="vc-preparacion__requisito">
    <div className="vc-preparacion__nombre"><h3>{requisito.nombre}</h3><Insignia texto={estado.texto} color={estado.color}/></div>
    <p className="vc-preparacion__para">Para: {requisito.necesario_para}</p>
    <p>{requisito.detalle}</p>
    {requisito.accion && <p>{requisito.accion}</p>}
    {requisito.tamano && <p className="vc-nota">Descarga aproximada: {requisito.tamano}</p>}
    {requisito.comando && <div className="vc-preparacion__comando">
      <pre tabIndex={0} aria-label={`Comando para ${requisito.nombre}`}><code>{requisito.comando}</code></pre>
      <button className="vc-boton" type="button" onClick={() => void copiar()} aria-label={`Copiar comando de ${requisito.nombre}`}>Copiar comando</button>
    </div>}
    {enlace && <a className="vc-preparacion__enlace" href={enlace} target="_blank" rel="noreferrer">Instrucciones de {requisito.nombre}<span className="vc-oculto"> (se abre en otra pestaña)</span></a>}
  </li>;
}
