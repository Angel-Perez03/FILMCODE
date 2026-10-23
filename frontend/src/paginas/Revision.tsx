import { lazy, Suspense, useState } from 'react';
import { baseProyecto, useDatos } from '../api';
import type { Archivo } from '../tipos';
import { fechaCorta, numero } from '../logica';
import { Cargando, ErrorVista, Insignia, Terminal, Vacio } from '../componentes/Comun';

const EditorCodigo = lazy(() => import('../componentes/EditorCodigo').then(m => ({ default: m.EditorCodigo })));

interface Captura { comando: string; ejecutado: boolean; motivo: string; salida: string[]; codigo: number | null; segundos: number; equipo?: string }
interface Registro { etiqueta: string; modelo: string; intento: number; segundos: number; tokens?: { entrada: number; salida: number }; errores: string[]; fecha: string }

export function ComandosVista({ nombre }: {nombre: string}) {
  const datos = useDatos<Captura[]>(`${baseProyecto(nombre)}/capturas`);
  if (datos.isPending) return <Cargando/>;
  const capturas = datos.data ?? [];
  return <div className="grid gap-8">
    <div>
      <h2 className="vc-subtitulo" style={{ marginBottom: 8 }}>Comandos reales</h2>
      <p className="vc-nota">{capturas.filter(c => c.ejecutado).length} de {capturas.length} comandos se corrieron en este equipo. Solo se corren comandos de verificación: nada que instale o borre.</p>
    </div>
    <ErrorVista error={datos.error}/>
    {capturas.length ? <div className="vc-comandos">
      {capturas.map((c, i) => <section key={i} aria-label={c.comando}>
        <Terminal real={c.ejecutado}>
          <span className="vc-terminal__prompt">$</span> {c.comando}{'\n'}{c.salida.join('\n') || 'Sin salida registrada.'}
        </Terminal>
        <p className="vc-comando__datos">
          <span className={c.codigo ? 'text-rojo' : undefined}>{c.motivo}</span>
          <span className="vc-cifras">{numero(c.segundos ?? 0, 2)} s</span>
          <span>código {c.codigo ?? '—'}</span>
          {c.equipo && <span>{c.equipo}</span>}
        </p>
      </section>)}
    </div> : !datos.error && <Vacio titulo="Sin comandos registrados"><p>Aparecen cuando se escribe el guion de una guía con los comandos de verificación activados.</p></Vacio>}
  </div>;
}

export function ModeloVista({ nombre }: {nombre: string}) {
  const datos = useDatos<Registro[]>(`${baseProyecto(nombre)}/llm`, 4000);
  if (datos.isPending) return <Cargando/>;
  const filas = datos.data ?? [];
  const segundos = filas.reduce((n, r) => n + r.segundos, 0), tokens = filas.reduce((n, r) => n + (r.tokens?.entrada ?? 0) + (r.tokens?.salida ?? 0), 0);
  return <div>
    <h2 className="vc-subtitulo" style={{ marginBottom: 8 }}>Actividad del modelo</h2>
    <p className="vc-nota" style={{ marginBottom: 24 }}>Las respuestas que salen de la caché no se anotan.</p>
    <ErrorVista error={datos.error}/>
    <dl className="vc-cifras-grandes">
      <div><dt>Llamadas</dt><dd>{filas.length}</dd></div>
      <div><dt>Minutos de modelo</dt><dd>{numero(segundos / 60)}</dd></div>
      <div><dt>Tokens</dt><dd>{numero(tokens, 0)}</dd></div>
    </dl>
    {filas.length ? <div className="vc-desplaza">
      <table className="vc-tabla">
        <thead><tr><th>Etapa y modelo</th><th>Intento</th><th>Tiempo</th><th>Tokens entrada / salida</th><th>Resultado</th></tr></thead>
        <tbody>{filas.map((r, i) => <tr key={i}>
          <td>{r.etiqueta}<small>{r.modelo} · {fechaCorta(r.fecha)}</small></td>
          <td>{r.intento}</td>
          <td>{numero(r.segundos)} s</td>
          <td>{numero(r.tokens?.entrada ?? 0, 0)} / {numero(r.tokens?.salida ?? 0, 0)}</td>
          <td>{r.errores?.length ? <span className="text-rojo">{r.errores.join(' · ')}</span> : <Insignia texto="correcto" color="verde"/>}</td>
        </tr>)}</tbody>
      </table>
    </div> : <Vacio titulo="Todavía no hay llamadas al modelo"/>}
  </div>;
}

export function CodigoVista({ nombre }: {nombre: string}) {
  const [seleccion, setSeleccion] = useState('');
  const arbol = useDatos<Archivo[]>(`${baseProyecto(nombre)}/codigo`);
  const ruta = seleccion || arbol.data?.[0]?.ruta || '';
  const archivo = useDatos<{ruta: string; contenido: string; lenguaje: string}>(`${baseProyecto(nombre)}/codigo/archivo?ruta=${encodeURIComponent(ruta)}`, undefined, Boolean(ruta));
  return <div>
    <h2 className="vc-subtitulo" style={{ marginBottom: 8 }}>Código de la fuente</h2>
    <p className="vc-nota" style={{ marginBottom: 24 }}>La copia del proyecto, en solo lectura. El original no se toca.</p>
    <ErrorVista error={arbol.error}/>
    <div className="vc-codigo-vista">
      <nav className="vc-arbol" aria-label="Archivos de la fuente">
        {arbol.isPending && <div className="p-4"><Cargando/></div>}
        {arbol.data?.map(a => <button key={a.ruta} aria-current={a.ruta === ruta ? 'true' : undefined} onClick={() => setSeleccion(a.ruta)}>
          <span>{a.ruta}</span><small>{numero(Math.max(1, a.bytes / 1000), 0)} KB</small>
        </button>)}
      </nav>
      <section className="min-w-0">
        <ErrorVista error={archivo.error}/>
        {archivo.data ? <Suspense fallback={<Cargando/>}>
          <EditorCodigo valor={archivo.data.contenido} lenguaje={archivo.data.lenguaje} etiqueta={`Código de ${ruta}`}/>
        </Suspense> : archivo.isPending && ruta ? <Cargando/> : <Vacio titulo="Elige un archivo"/>}
      </section>
    </div>
  </div>;
}
