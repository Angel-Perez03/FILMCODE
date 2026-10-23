import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { refrescarSalud, useDatos } from '../api';
import type { Ajustes, Salud, Voces } from '../tipos';
import { avisar, Cargando, ErrorVista, Insignia } from '../componentes/Comun';
import { Selector } from '../componentes/Controles';
import { PreparacionEquipo } from '../componentes/PreparacionEquipo';

export function AjustesVista() {
  const cliente = useQueryClient();
  const ajustes = useDatos<Ajustes>('/ajustes'), salud = useDatos<Salud>('/salud', 10000), voces = useDatos<Voces>('/voces');
  const [proveedor, setProveedor] = useState<'edge' | 'voicestudio'>('edge');
  const [voz, setVoz] = useState(''), [texto, setTexto] = useState('Hola, soy la voz de tu próximo video. Vamos a explicar tu código, paso a paso.');
  const [audio, setAudio] = useState(''), [probando, setProbando] = useState(false);
  const disponibles = proveedor === 'edge' ? voces.data?.edge ?? [] : Array.isArray(voces.data?.voicestudio) ? voces.data.voicestudio : [];
  const vozElegida = voz || (proveedor === 'edge' ? ajustes.data?.voz.edge_voz : ajustes.data?.voz.voicestudio_voz) || disponibles[0]?.id || '';
  useEffect(() => () => { if (audio) URL.revokeObjectURL(audio); }, [audio]);
  async function probarVoz() {
    setProbando(true);
    try {
      const respuesta = await fetch('/api/voces/prueba', { method: 'POST', headers: { 'X-VideoCodigo': '1', 'Content-Type': 'application/json' }, body: JSON.stringify({ proveedor, voz: vozElegida, texto }) });
      if (!respuesta.ok) { const datos = await respuesta.json() as {error: string}; throw new Error(datos.error); }
      setAudio(URL.createObjectURL(await respuesta.blob()));
    } catch (e) { avisar((e as Error).message, true); } finally { setProbando(false); }
  }
  if (ajustes.isPending) return <div className="vc-pagina"><Cargando/></div>;
  const servicios = [['ollama', 'Ollama'], ['voicestudio', 'VoiceStudio']] as const;
  return <div className="vc-pagina">
    <div className="vc-cabeza">
      <div>
        <h1 className="titulo">Ajustes</h1>
        <p className="vc-cabeza__meta">{ajustes.data?.capacidades?.modo === 'docker'
          ? 'Para cambiar la configuración, edita configuracion.local y recrea el contenedor cuando no haya trabajos activos.'
          : 'Para cambiar la configuración, edita .env y reinicia la API. La app no modifica ese archivo.'}</p>
      </div>
      <button className="vc-boton" onClick={() => { void refrescarSalud(cliente).catch((e: Error) => avisar(e.message, true)); void voces.refetch(); }}>Probar los servicios</button>
    </div>
    <ErrorVista error={ajustes.error}/>
    <PreparacionEquipo/>
    <div className="vc-ajustes">
      <section aria-labelledby="servicios">
        <h2 id="servicios" className="vc-subtitulo">Servicios de este equipo</h2>
        {servicios.map(([clave, nombre]) => <div key={clave} className="vc-servicio">
          <div className="flex flex-wrap items-center justify-between gap-4"><strong className="font-semibold">{nombre}</strong><Insignia texto={salud.data?.[clave].listo ? 'listo' : salud.data ? 'apagado' : 'consultando'} color={salud.data?.[clave].listo ? 'verde' : 'gris'}/></div>
          <p>{salud.data?.[clave].mensaje ?? 'Consultando…'}</p>
        </div>)}
        <div className="vc-servicio">
          <div className="flex flex-wrap items-center justify-between gap-4"><strong className="font-semibold">ffmpeg</strong><Insignia texto={salud.data?.ffmpeg ? 'listo' : 'no está'} color={salud.data?.ffmpeg ? 'verde' : 'gris'}/></div>
          <p>Hace las miniaturas, las hojas de revisión y el video final.</p>
        </div>
        <p className="vc-nota">Estos botones solo consultan el estado. Ollama y VoiceStudio los enciendes y apagas tú.</p>
      </section>
      <section aria-labelledby="modelos">
        <h2 id="modelos" className="vc-subtitulo">Modelos de Ollama</h2>
        {salud.data?.ollama.modelos.length ? <ul className="vc-modelos">
          {salud.data.ollama.modelos.map(m => <li key={m}><code className="codigo">{m}</code>{m === ajustes.data?.modelo.modelo && <Insignia texto="predeterminado" color="verde"/>}{salud.data?.ollama.cargados?.includes(m) && <Insignia texto="cargado en memoria" color="amarillo"/>}</li>)}
        </ul> : <p className="vc-nota">No se pudo consultar la lista: Ollama está apagado o no responde. La app nunca descarga modelos.</p>}
      </section>
      <section aria-labelledby="prueba-voz" className="grid gap-4 content-start">
        <h2 id="prueba-voz" className="vc-subtitulo" style={{ margin: 0 }}>Prueba de voz</h2>
        <p className="vc-nota">Solo se genera audio cuando pulsas «Probar voz», con 200 caracteres como máximo.</p>
        <div className="vc-dos-columnas">
          <div className="vc-campo"><span className="vc-campo__etiqueta">Proveedor</span><Selector etiqueta="Proveedor de voz" valor={proveedor} cambiar={v => { setProveedor(v as 'edge' | 'voicestudio'); setVoz(''); }} opciones={[{ valor: 'edge', texto: 'Edge', detalle: 'necesita internet' }, { valor: 'voicestudio', texto: 'VoiceStudio', detalle: 'en este equipo' }]}/></div>
          <div className="vc-campo"><span className="vc-campo__etiqueta">Voz</span><Selector etiqueta="Voz" valor={vozElegida} cambiar={setVoz} opciones={[...(disponibles.some(v => v.id === vozElegida) || !vozElegida ? [] : [{ valor: vozElegida, texto: vozElegida }]), ...disponibles.map(v => ({ valor: v.id, texto: v.nombre, detalle: v.acento }))]}/></div>
        </div>
        <label className="vc-campo">
          <span className="vc-campo__etiqueta">Texto de prueba</span>
          <textarea className="vc-campo__entrada" rows={3} maxLength={200} value={texto} onChange={e => setTexto(e.target.value)}/>
          <span className="vc-campo__ayuda vc-cifras">{texto.length} / 200</span>
        </label>
        <div className="vc-fila-botones">
          <button className="vc-boton vc-boton--principal" disabled={probando || !vozElegida || !texto.trim() || Boolean(salud.data?.trabajo) || (proveedor === 'voicestudio' && !salud.data?.voicestudio.listo)} onClick={() => void probarVoz()}>{probando ? 'Generando el audio…' : 'Probar voz'}</button>
          {salud.data?.trabajo && <span className="vc-nota">Espera a que termine el trabajo en curso.</span>}
        </div>
        {audio && <audio key={audio} controls src={audio} aria-label="Prueba de voz generada" className="w-full"/>}
        <ErrorVista error={voces.error}/>
      </section>
      <section aria-labelledby="configuracion">
        <h2 id="configuracion" className="vc-subtitulo">Configuración efectiva</h2>
        {ajustes.data && <dl className="vc-datos">
          {Object.entries(ajustes.data.modelo).map(([clave, valor]) => <Par key={`m-${clave}`} clave={`modelo · ${clave}`} valor={String(valor)}/>)}
          {Object.entries(ajustes.data.voz).map(([clave, valor]) => <Par key={`v-${clave}`} clave={`voz · ${clave}`} valor={String(valor)}/>)}
          <Par clave="clave de OpenAI" valor={ajustes.data.claves.openai ? 'configurada: sí' : 'configurada: no'}/>
          <Par clave="clave de VoiceStudio" valor={ajustes.data.claves.voicestudio ? 'configurada: sí' : 'configurada: no'}/>
        </dl>}
      </section>
    </div>
  </div>;
}

function Par({ clave, valor }: {clave: string; valor: string}) {
  return <><dt>{clave}</dt><dd>{valor || '—'}</dd></>;
}
