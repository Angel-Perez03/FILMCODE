import { useEffect, useState } from 'react';
import { useBlocker } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowDown, ArrowUp, CircleAlert, Copy, Plus, Trash2 } from 'lucide-react';
import { baseProyecto, enviar, ErrorAPI, useDatos } from '../api';
import type { Escena, Esquema, Guion, Json } from '../tipos';
import { cambiarNarracion, narraciones, objeto } from '../logica';
import { avisar, Cargando, ErrorVista, Insignia, Mensaje } from '../componentes/Comun';
import { useConfirmar } from '../componentes/Controles';
import { EditorCodigo } from '../componentes/EditorCodigo';
import { Icono } from '../componentes/Icono';

const deEscena = (n: number) => new RegExp(`^Escena ${n}(?:\\s|:)`);

export function GuionEditor({ nombre, ocupado }: {nombre: string; ocupado: boolean}) {
  const ruta = `${baseProyecto(nombre)}/guion`;
  const consulta = useDatos<{guion: Guion; errores: string[]; origen: string}>(ruta);
  const esquema = useDatos<Esquema>('/esquema');
  const [guion, setGuion] = useState<Guion | null>(null), [seleccion, setSeleccion] = useState(0);
  const [sucio, setSucio] = useState(false), [errores, setErrores] = useState<string[]>([]), [error, setError] = useState<Error | null>(null);
  const [procesando, setProcesando] = useState(false), [jsonError, setJsonError] = useState(false), [documentoJSON, setDocumentoJSON] = useState(false);
  const cliente = useQueryClient(), confirmar = useConfirmar();
  const bloqueo = useBlocker(sucio || jsonError);
  const estadoBloqueo = bloqueo.state;
  useEffect(() => {
    if (estadoBloqueo !== 'blocked') return;
    void confirmar({ titulo: '¿Salir sin guardar?', texto: <p>Hay cambios en el guion que todavía no guardaste. Si sales, se pierden.</p>, aceptar: 'Salir y descartar', cancelar: 'Seguir editando', peligro: true })
      .then(salir => { if (salir) bloqueo.proceed?.(); else bloqueo.reset?.(); });
    // Se pregunta una vez por cada bloqueo, no en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estadoBloqueo]);
  useEffect(() => { const salir = (e: BeforeUnloadEvent) => { if (sucio || jsonError) e.preventDefault(); }; window.addEventListener('beforeunload', salir); return () => window.removeEventListener('beforeunload', salir); }, [sucio, jsonError]);
  useEffect(() => { if (consulta.data && !sucio && !jsonError) { setGuion(consulta.data.guion); setErrores(consulta.data.errores); } }, [consulta.data, sucio, jsonError]);
  if (consulta.isPending) return <Cargando/>;
  if (!guion) return <ErrorVista error={consulta.error} reintentar={() => void consulta.refetch()}/>;
  const estructuraValida = Array.isArray(guion.escenas) && guion.escenas.every(e => objeto(e) && typeof e.tipo === 'string');
  const escenas = estructuraValida ? guion.escenas : [];
  const escena = escenas[seleccion];
  const limite = esquema.data?.limites.texto ?? 900;
  function cambiar(nuevo: Guion) { setGuion(nuevo); setSucio(true); setErrores([]); }
  function cambiarEscena(nueva: Escena) { if (guion) cambiar({ ...guion, escenas: escenas.map((e, i) => i === seleccion ? nueva : e) }); }
  function mover(delta: number) { if (!guion) return; const nuevas = [...escenas]; [nuevas[seleccion], nuevas[seleccion + delta]] = [nuevas[seleccion + delta], nuevas[seleccion]]; cambiar({ ...guion, escenas: nuevas }); setSeleccion(seleccion + delta); }
  async function elegir(i: number) {
    if (jsonError && !await confirmar({ titulo: '¿Descartar el JSON?', texto: <p>Hay cambios en el JSON de la escena que no aplicaste.</p>, aceptar: 'Descartar', peligro: true })) return;
    setSeleccion(i); setJsonError(false);
  }
  async function validar(guardar: boolean) {
    setProcesando(true); setError(null);
    try {
      const validacion = await enviar<{errores: string[]}>(`${ruta}/validar`, guion);
      setErrores(validacion.errores);
      if (!validacion.errores.length && guardar) { await enviar(ruta, guion, 'PUT'); setSucio(false); await cliente.invalidateQueries(); avisar('Guion guardado. La versión anterior quedó en guion_versiones y los videos existentes quedan desactualizados.'); }
      else if (!validacion.errores.length) avisar('El guion es válido.');
    } catch (e) { setError(e as Error); if (e instanceof ErrorAPI) setErrores(e.errores); } finally { setProcesando(false); }
  }
  const erroresEscena = errores.filter(e => deEscena(seleccion + 1).test(e));
  const globales = errores.filter(e => !/^Escena \d+/.test(e));
  return <fieldset className="grid gap-6 border-0 p-0 m-0 min-w-0" disabled={procesando}>
    <div className="vc-fila-botones justify-between">
      <span className="flex flex-wrap items-center gap-4"><span className="vc-cifras">{escenas.length} / {esquema.data?.limites.escenas ?? 60} escenas</span><Insignia texto={sucio || jsonError ? 'cambios sin guardar' : 'guardado'} color={sucio || jsonError ? 'amarillo' : 'verde'}/></span>
      <span className="vc-fila-botones">
        <button className="vc-boton vc-boton--texto" onClick={() => void (async () => { if (!jsonError || await confirmar({ titulo: '¿Descartar el JSON?', texto: <p>Hay cambios en el JSON que no aplicaste.</p>, aceptar: 'Descartar', peligro: true })) { setJsonError(false); setDocumentoJSON(!documentoJSON); } })()}>{documentoJSON ? 'Volver a las escenas' : 'Editar el documento completo'}</button>
        <button className="vc-boton" disabled={procesando || jsonError} onClick={() => void validar(false)}>Validar</button>
        <button className="vc-boton vc-boton--principal" disabled={ocupado || procesando || jsonError || !sucio} onClick={() => void validar(true)}>{procesando ? 'Comprobando…' : 'Guardar guion'}</button>
      </span>
    </div>
    {ocupado && <Mensaje tono="aviso">Hay un trabajo en curso en este proyecto. Puedes revisar el guion; guardar se habilita cuando termine.</Mensaje>}
    {consulta.data?.origen === 'con_errores' && <Mensaje tono="aviso">El modelo escribió un guion con errores: corrígelo aquí.</Mensaje>}
    <ErrorVista error={error}/>
    {globales.length > 0 && <ul className="vc-errores" role="alert">{globales.map((e, i) => <li key={i}><CircleAlert aria-hidden="true"/>{e}</li>)}</ul>}
    {!estructuraValida && !documentoJSON && <Mensaje tono="aviso">La lista de escenas no es válida. Usa «Editar el documento completo» para corregirla.</Mensaje>}
    {documentoJSON ? <JSONAplicable valor={guion} aplicar={valor => { if (!objeto(valor) || !Array.isArray(valor.escenas) || valor.escenas.some(e => !objeto(e) || typeof e.tipo !== 'string')) throw new Error('El documento necesita una lista de escenas, cada una con su tipo.'); cambiar(valor as unknown as Guion); setSeleccion(0); }} invalido={setJsonError}/>
      : <div className="vc-editor">
        <div className="vc-editor__lista">
          <div className="vc-editor__lista-cabeza">
            <span className="pequeno text-gris">Escenas</span>
            <button className="vc-boton vc-boton--icono vc-boton--chico" disabled={jsonError || !estructuraValida || escenas.length >= (esquema.data?.limites.escenas ?? 60)} aria-label="Agregar escena" onClick={() => { cambiar({ ...guion, escenas: [...escenas, { tipo: 'idea', narracion: [''] }] }); setSeleccion(escenas.length); }}><Plus aria-hidden="true"/></button>
          </div>
          <ol className="vc-escenas" aria-label="Escenas del guion">
            {escenas.map((e, i) => {
              const textos = narraciones(e), caracteres = textos.reduce((n, t) => n + t.texto.length, 0);
              const propios = errores.filter(x => deEscena(i + 1).test(x));
              return <li key={i}>
                <button className="vc-escena" aria-current={seleccion === i ? 'true' : undefined} onClick={() => void elegir(i)}>
                  <Icono nombre={typeof e.icono === 'string' && e.tipo === 'portada' ? e.icono : e.tipo}/>
                  <span className="vc-escena__tipo pequeno">{i + 1} · {e.tipo}{typeof e.titulo === 'string' && e.titulo ? ` · ${e.titulo}` : ''}</span>
                  <span className="vc-escena__cifras pequeno">{caracteres} car. · {Math.round(caracteres / 14.8)} s</span>
                  <span className="vc-escena__frase">{textos[0]?.texto.replace(/\[\[.*?\]\]/g, '') || 'Sin narración'}</span>
                  {propios.length > 0 && <span className="vc-escena__error pequeno"><CircleAlert aria-hidden="true"/>{propios.length === 1 ? propios[0] : `${propios.length} errores`}</span>}
                </button>
              </li>;
            })}
          </ol>
        </div>
        <section className="vc-editor__detalle" aria-label={escena ? `Escena ${seleccion + 1}` : 'Escena'}>
          {escena ? <>
            <div className="vc-fila-botones justify-between">
              <h2 className="vc-subtitulo" style={{ margin: 0 }}>Escena {seleccion + 1} · {escena.tipo}</h2>
              <span className="vc-fila-botones">
                <button className="vc-boton vc-boton--icono" aria-label="Subir escena" disabled={jsonError || seleccion === 0} onClick={() => mover(-1)}><ArrowUp aria-hidden="true"/></button>
                <button className="vc-boton vc-boton--icono" aria-label="Bajar escena" disabled={jsonError || seleccion === escenas.length - 1} onClick={() => mover(1)}><ArrowDown aria-hidden="true"/></button>
                <button className="vc-boton vc-boton--icono" aria-label="Duplicar escena" disabled={jsonError || escenas.length >= 60} onClick={() => { const nuevas = [...escenas]; nuevas.splice(seleccion + 1, 0, structuredClone(escena)); cambiar({ ...guion, escenas: nuevas }); setSeleccion(seleccion + 1); }}><Copy aria-hidden="true"/></button>
                <button className="vc-boton vc-boton--icono vc-boton--peligro" aria-label="Borrar escena" disabled={jsonError} onClick={() => void confirmar({ titulo: `¿Borrar la escena ${seleccion + 1}?`, texto: <p>El cambio se aplica al guardar el guion.</p>, aceptar: 'Borrar escena', peligro: true }).then(si => { if (si) { cambiar({ ...guion, escenas: escenas.filter((_, i) => i !== seleccion) }); setSeleccion(Math.max(0, seleccion - 1)); } })}><Trash2 aria-hidden="true"/></button>
              </span>
            </div>
            {erroresEscena.length > 0 && <ul className="vc-errores" role="alert">{erroresEscena.map(e => <li key={e}><CircleAlert aria-hidden="true"/>{e}</li>)}</ul>}
            <label className="vc-campo">
              <span className="vc-campo__etiqueta">Título del video</span>
              <input className="vc-campo__entrada" value={guion.titulo ?? ''} disabled={jsonError} onChange={e => cambiar({ ...guion, titulo: e.target.value })}/>
            </label>
            <p className="vc-nota">Las marcas [[nombre]] sincronizan la animación y no se pronuncian.</p>
            {narraciones(escena).map(n => <label key={n.ruta.join('.')} className="vc-narracion">
              <span className="vc-narracion__cabeza"><span>{n.ruta.join(' › ')}</span><span className={`vc-cifras${n.texto.length > limite ? ' text-rojo' : ''}`}>{n.texto.length} / {limite}</span></span>
              <textarea className="vc-campo__entrada" disabled={jsonError} value={n.texto} onChange={e => cambiarEscena(cambiarNarracion(escena, n.ruta, e.target.value))}/>
            </label>)}
            {narraciones(escena).length === 0 && <p className="vc-nota">Esta escena no tiene narración. Puedes agregarla en su JSON.</p>}
            {escena.tipo === 'terminal' && Array.isArray(escena.comandos) && <ul className="grid gap-2 m-0 p-0 list-none">
              {escena.comandos.map((c: Json, i) => objeto(c) && <li key={i} className="flex flex-wrap items-center gap-4"><code className="codigo">{String(c.comando ?? '')}</code><Insignia texto={c.salida_real ? 'salida real de este equipo' : 'salida de ejemplo'} color={c.salida_real ? 'verde' : 'gris'}/></li>)}
            </ul>}
            {typeof escena.fragmento === 'string' && guion.fragmentos?.[escena.fragmento] && <FragmentoVista nombre={nombre} fragmento={guion.fragmentos[escena.fragmento]} escena={escena}/>}
            <div className="grid gap-2">
              <span className="vc-campo__etiqueta">Estructura de la escena (JSON)</span>
              <JSONAplicable key={seleccion} valor={escena} aplicar={valor => { if (!objeto(valor) || typeof valor.tipo !== 'string') throw new Error('La escena debe ser un objeto con un tipo.'); cambiarEscena(valor as Escena); }} invalido={setJsonError}/>
              {esquema.data?.escenas[escena.tipo] && <p className="vc-nota">Campos obligatorios de {escena.tipo}: {esquema.data.escenas[escena.tipo].join(', ')}.</p>}
            </div>
          </> : <p className="vc-nota">No hay escenas. Agrega una o corrige el documento completo.</p>}
        </section>
      </div>}
  </fieldset>;
}

function JSONAplicable({ valor, aplicar, invalido }: {valor: unknown; aplicar: (valor: Json) => void; invalido: (v: boolean) => void}) {
  const original = JSON.stringify(valor, null, 2);
  const [texto, setTexto] = useState(original), [error, setError] = useState('');
  useEffect(() => { setTexto(original); setError(''); invalido(false); }, [original]); // eslint-disable-line react-hooks/exhaustive-deps
  function confirmar() { try { const datos = JSON.parse(texto) as Json; aplicar(datos); setError(''); invalido(false); } catch (e) { setError((e as Error).message); invalido(true); } }
  return <div className="grid gap-3">
    <EditorCodigo valor={texto} cambiar={nuevo => { setTexto(nuevo); invalido(nuevo !== original); }} etiqueta="JSON de la escena"/>
    <div className="vc-fila-botones">
      <button className="vc-boton" disabled={texto === original} onClick={confirmar}>Aplicar cambios del JSON</button>
      {texto !== original && <span className="vc-insignia vc-insignia--amarillo">aplica el JSON antes de validar o guardar</span>}
    </div>
    {error && <p role="alert" className="m-0 text-rojo">{error}</p>}
  </div>;
}

function FragmentoVista({ nombre, fragmento, escena }: {nombre: string; fragmento: NonNullable<Guion['fragmentos']>[string]; escena: Escena}) {
  const codigo = useDatos<{contenido: string}>(`${baseProyecto(nombre)}/codigo/archivo?ruta=${encodeURIComponent(fragmento.archivo.replace(/^codigo\//, ''))}`);
  const rangos = Array.isArray(escena.lineas) ? escena.lineas.flatMap(l => objeto(l) && typeof l.desde === 'number' ? [[l.desde, typeof l.hasta === 'number' ? l.hasta : l.desde]] : []) : [];
  return <div className="grid gap-2">
    <span className="vc-campo__etiqueta">Fragmento: {fragmento.archivo}</span>
    <ErrorVista error={codigo.error}/>
    <div className="vc-fragmento codigo">{codigo.data?.contenido.split('\n').map((linea, i) => {
      const n = i + 1;
      if (n < (fragmento.desde ?? 1) || n > (fragmento.hasta ?? Infinity)) return null;
      const resaltada = rangos.some(r => n >= Number(r[0]) && n <= Number(r[1] ?? r[0]));
      return <div key={n} className={resaltada ? 'vc-fragmento__resaltada' : undefined}><span>{n}</span><code>{linea || ' '}</code></div>;
    })}</div>
  </div>;
}
