import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { baseProyecto, enviar, refrescarSalud, useDatos } from '../api';
import type { Ajustes, Detalle, FaseRender, OpcionesTrabajo, Salud, Trabajo, Voces } from '../tipos';
import { AYUDA_PRIORIDAD, configRenderInicial, describirCalidad, describirVoz, duracion, fechaCorta, numero, opcionesDeVoz, opcionesVoz, separarVoz, siguiente, tiempoLegible, vozInicial } from '../logica';
import { avisar, Insignia, Mensaje, Progreso, Terminal } from '../componentes/Comun';
import { Selector, useConfirmar } from '../componentes/Controles';
import { OpcionesRender } from '../componentes/OpcionesRender';
import { RecursosTrabajo } from '../componentes/RecursosTrabajo';
import { aplicarFlip } from '../movimiento/flip';

const ETIQUETAS: Record<string, string> = { retomar: 'Retomar', reintentar: 'Reintentar', corregir: 'Corregir el guion', guion: 'Escribir el guion', render: 'Renderizar video', ver: 'Ver el video', cancelar: 'Cancelar' };
const FASES_RENDER = [
  { id: 'voces', titulo: 'Preparar voces' },
  { id: 'animaciones', titulo: 'Animar escenas' },
  { id: 'exportacion', titulo: 'Exportar video' },
] as const;
const TITULOS_RENDER: Record<FaseRender, string> = { voces: 'Preparando voces', animaciones: 'Animando escenas con Manim', exportacion: 'Exportando el video', terminado: 'Video terminado' };

export function Resumen({ proyecto: p, ir }: {proyecto: Detalle; ir: (vista: string) => void}) {
  const salud = useDatos<Salud>('/salud', 10000), trabajos = useDatos<Trabajo[]>('/trabajos');
  const ajustes = useDatos<Ajustes>('/ajustes'), voces = useDatos<Voces>('/voces');
  const prioridadDinamica = ajustes.data?.capacidades?.prioridad_dinamica !== false;
  const enDocker = ajustes.data?.capacidades?.modo === 'docker';
  const [voz, setVoz] = useState('');
  const [calidad, setCalidad] = useState<string>(() => configRenderInicial(p.preferencias?.calidad));
  const [prioridadBaja, setPrioridadBaja] = useState(p.preferencias?.prioridad_baja ?? true);
  const [cambiandoPrioridad, setCambiandoPrioridad] = useState(false);
  const [duracionObjetivo, setDuracionObjetivo] = useState(() => p.preferencias?.duracion_objetivo_minutos?.toString() ?? '');
  const [entradaDuracionInvalida, setEntradaDuracionInvalida] = useState(false);
  const [guardandoDuracion, setGuardandoDuracion] = useState(false);
  const [velocidadVoz, setVelocidadVoz] = useState(() => (p.preferencias?.velocidad_voz ?? 1).toString());
  const [velocidadAnimaciones, setVelocidadAnimaciones] = useState(() => (p.preferencias?.velocidad_animaciones ?? 1).toString());
  const [vozFluida, setVozFluida] = useState(p.preferencias?.voz_fluida ?? false);
  const [vozInvalida, setVozInvalida] = useState(false), [animacionesInvalidas, setAnimacionesInvalidas] = useState(false);
  const [guardandoVelocidades, setGuardandoVelocidades] = useState(false);
  const [procesando, setProcesando] = useState(false), [ahora, setAhora] = useState(Date.now());
  const cliente = useQueryClient(), confirmar = useConfirmar();
  const trabajo = trabajos.data?.find(t => t.id === p.trabajo?.id) ?? p.trabajo;
  const ultimoTrabajo = trabajos.data?.filter(t => t.proyecto === p.nombre).sort((a, b) => b.inicio.localeCompare(a.inicio))[0];
  const registro = useDatos<{lineas: string[]}>(`${baseProyecto(p.nombre)}/log/${calidad}?lineas=200`, undefined, p.situacion === 'error');
  const lineas = trabajo?.lineas.length ? trabajo.lineas : ultimoTrabajo?.lineas.length ? ultimoTrabajo.lineas : registro.data?.lineas ?? [];
  const accion = p.tiene_guion && !p.situacion.startsWith('en_curso') ? 'render' : siguiente(p);
  const ocupado = accion === 'cancelar', externo = p.situacion === 'en_curso_externo';
  const enRender = ocupado && p.etapa.startsWith('renderizando');
  const renderTerminadoVigente = !ocupado && p.situacion === 'listo' && p.estado.fase_render === 'terminado'
    && p.videos.some(v => v.calidad === p.etapa && !v.desactualizado);
  const faseRender = enRender || renderTerminadoVigente ? p.estado.fase_render : undefined;
  const indiceFase = faseRender === 'terminado' ? FASES_RENDER.length : FASES_RENDER.findIndex(f => f.id === faseRender);
  const vocesEstado = p.estado.voces;
  const frasesSincronizadas = (vocesEstado?.cacheados ?? 0) + (vocesEstado?.generados ?? 0);
  const prioridadActual = trabajo?.prioridad_baja;
  const prioridadElegida = ocupado ? prioridadActual == null ? '' : prioridadActual ? 'baja' : 'alta' : prioridadBaja ? 'baja' : 'alta';
  const duracionGuardada = p.preferencias?.duracion_objetivo_minutos ?? null;
  const duracionEstimada = p.estado.guion?.duracion_estimada_segundos ?? (p.estado.guion?.caracteres ? p.estado.guion.caracteres / 14.8 : undefined);
  const minutosObjetivo = duracionObjetivo.trim() === '' ? null : Number(duracionObjetivo);
  const duracionValida = !entradaDuracionInvalida && (minutosObjetivo == null || (Number.isFinite(minutosObjetivo) && minutosObjetivo >= 1 && minutosObjetivo <= 120));
  const duracionModificada = minutosObjetivo !== duracionGuardada;
  const inicioBloqueadoPorDuracion = guardandoDuracion || duracionModificada || !duracionValida;
  const velocidadVozGuardada = p.preferencias?.velocidad_voz ?? 1, velocidadAnimacionesGuardada = p.preferencias?.velocidad_animaciones ?? 1;
  const vozFluidaGuardada = p.preferencias?.voz_fluida ?? false;
  const factorVoz = Number(velocidadVoz), factorAnimaciones = Number(velocidadAnimaciones);
  const velocidadVozValida = !vozInvalida && velocidadVoz.trim() !== '' && Number.isFinite(factorVoz) && factorVoz >= 0.75 && factorVoz <= 1.5;
  const velocidadAnimacionesValida = !animacionesInvalidas && velocidadAnimaciones.trim() !== '' && Number.isFinite(factorAnimaciones) && factorAnimaciones >= 0.5 && factorAnimaciones <= 2;
  const velocidadesValidas = velocidadVozValida && velocidadAnimacionesValida;
  const velocidadesModificadas = factorVoz !== velocidadVozGuardada || factorAnimaciones !== velocidadAnimacionesGuardada || vozFluida !== vozFluidaGuardada;
  const inicioBloqueado = inicioBloqueadoPorDuracion || guardandoVelocidades || velocidadesModificadas || !velocidadesValidas;
  useEffect(() => { setPrioridadBaja(p.preferencias?.prioridad_baja ?? true); }, [p.nombre, p.preferencias?.prioridad_baja]);
  useEffect(() => { setCalidad(configRenderInicial(p.preferencias?.calidad)); }, [p.nombre, p.preferencias?.calidad]);
  useEffect(() => { setDuracionObjetivo(p.preferencias?.duracion_objetivo_minutos?.toString() ?? ''); setEntradaDuracionInvalida(false); }, [p.nombre, p.preferencias?.duracion_objetivo_minutos]);
  useEffect(() => {
    setVelocidadVoz((p.preferencias?.velocidad_voz ?? 1).toString());
    setVelocidadAnimaciones((p.preferencias?.velocidad_animaciones ?? 1).toString());
    setVozFluida(p.preferencias?.voz_fluida ?? false);
    setVozInvalida(false); setAnimacionesInvalidas(false);
  }, [p.nombre, p.preferencias?.velocidad_voz, p.preferencias?.velocidad_animaciones, p.preferencias?.voz_fluida]);
  useEffect(() => { if (ajustes.data) setVoz(v => v || vozInicial(ajustes.data, p.preferencias)); }, [ajustes.data, p.preferencias]);
  useEffect(() => { if (!ocupado) return; const reloj = setInterval(() => setAhora(Date.now()), 1000); return () => clearInterval(reloj); }, [ocupado]);
  // Cuando el último trabajo pasa de corriendo a terminado, la barra barre la fila una vez antes de irse.
  const [barrido, setBarrido] = useState(false), previo = useRef(ultimoTrabajo);
  useEffect(() => {
    const antes = previo.current;
    previo.current = ultimoTrabajo;
    if (antes?.id === ultimoTrabajo?.id && antes?.estado === 'corriendo' && ultimoTrabajo?.estado === 'terminado') setBarrido(true);
  }, [ultimoTrabajo]);
  const mostrarBarrido = barrido && !ocupado;
  useEffect(() => { if (!mostrarBarrido) return; const reloj = setTimeout(() => setBarrido(false), 1600); return () => clearTimeout(reloj); }, [mostrarBarrido]);
  const transcurrido = trabajo ? Math.max(0, (ahora - new Date(trabajo.inicio).getTime()) / 1000) : 0;
  // Los contadores de voces pertenecen a esa fase; no representan un porcentaje del video completo.
  const progreso = faseRender ? faseRender === 'animaciones' ? p.estado.progreso : null : (trabajo ? trabajo.progreso : p.progreso) || null;
  const restante = !faseRender && trabajo && progreso && progreso > 0 && progreso < 100 ? transcurrido * (100 - progreso) / progreso : null;
  const necesitaModelo = accion === 'guion' || (['retomar', 'reintentar'].includes(accion) && !p.tiene_guion);
  const proveedor = voz ? separarVoz(voz).proveedor : 'voicestudio', vozLocal = proveedor === 'voicestudio';
  const opcionesVoces = opcionesVoz(ajustes.data, voces.data);
  const nombreVoz = opcionesVoces.find(opcion => opcion.valor === voz)?.texto ?? describirVoz(proveedor);
  const bloqueado = necesitaModelo && salud.data && !salud.data.ollama.listo ? salud.data.ollama.mensaje
    : accion === 'render' && vozLocal && salud.data && !salud.data.voicestudio.listo ? salud.data.voicestudio.mensaje : '';
  const video = [...p.videos].sort((a, b) => b.fecha.localeCompare(a.fecha))[0];
  const explicacion: Record<string, string> = {
    cancelar: `${externo ? 'Lo lanzó una terminal fuera de la app; el progreso sale de estado.json.' : 'Puedes seguir usando la app.'}${prioridadActual == null ? '' : ` El trabajo corre con prioridad ${prioridadActual ? 'baja' : 'alta'}.`}`,
    retomar: `El estado dice «${p.etapa}», pero ningún proceso está trabajando. Lo que ya se hizo quedó en caché.`,
    reintentar: p.mensaje || 'El último trabajo falló.',
    corregir: 'El modelo escribió un guion con errores: corrígelo en la pestaña Guion.',
    guion: 'Un modelo local en Ollama escribe el guion. Tarda de 10 a 30 minutos y, si se corta, retoma donde quedó.',
    render: 'Elige cómo quieres el video y renderiza cuando estén listas las opciones. La resolución y los cuadros por segundo se eligen por separado de la voz.',
    ver: 'El video está al día. Puedes verlo con subtítulos, capítulos y la transcripción.',
  };

  async function lanzar(elegidas: OpcionesTrabajo) {
    if (inicioBloqueado) return;
    const opciones: OpcionesTrabajo = { ...elegidas, ...(elegidas.voz ? {} : opcionesDeVoz(voz)), prioridad_baja: prioridadBaja, velocidad_voz: factorVoz, velocidad_animaciones: factorAnimaciones, voz_fluida: vozFluida };
    setProcesando(true);
    try { await enviar(`${baseProyecto(p.nombre)}/trabajos`, opciones); await cliente.invalidateQueries(); avisar('Trabajo iniciado. Puedes seguirlo aquí o en la barra de arriba.'); }
    catch (e) { avisar((e as Error).message, true); } finally { setProcesando(false); }
  }
  async function guardarDuracion() {
    if (ocupado || procesando || guardandoDuracion || guardandoVelocidades || !duracionValida || !duracionModificada) return;
    setGuardandoDuracion(true);
    try {
      const preferencia = await enviar<{duracion_objetivo_minutos: number | null}>(`${baseProyecto(p.nombre)}/duracion`, { duracion_objetivo_minutos: minutosObjetivo });
      cliente.setQueryData<Detalle>([baseProyecto(p.nombre)], actual => actual ? { ...actual, preferencias: { ...actual.preferencias, ...preferencia } } : actual);
      setDuracionObjetivo(preferencia.duracion_objetivo_minutos?.toString() ?? '');
      await cliente.invalidateQueries();
      avisar('Duración guardada. Se aplicará al generar un guion nuevo.');
    } catch (e) { avisar((e as Error).message, true); } finally { setGuardandoDuracion(false); }
  }
  async function guardarVelocidades() {
    if (ocupado || procesando || guardandoVelocidades || guardandoDuracion || cambiandoPrioridad || !velocidadesValidas || !velocidadesModificadas) return;
    setGuardandoVelocidades(true);
    try {
      const preferencia = await enviar<{velocidad_voz: number; velocidad_animaciones: number; voz_fluida: boolean}>(`${baseProyecto(p.nombre)}/velocidades`, { velocidad_voz: factorVoz, velocidad_animaciones: factorAnimaciones, voz_fluida: vozFluida });
      cliente.setQueryData<Detalle>([baseProyecto(p.nombre)], actual => actual ? { ...actual, preferencias: { ...actual.preferencias, ...preferencia } } : actual);
      setVelocidadVoz(preferencia.velocidad_voz.toString()); setVelocidadAnimaciones(preferencia.velocidad_animaciones.toString());
      setVozFluida(preferencia.voz_fluida);
      await cliente.invalidateQueries();
      avisar('Velocidades guardadas. Se aplicarán al próximo render.');
    } catch (e) { avisar((e as Error).message, true); } finally { setGuardandoVelocidades(false); }
  }
  async function reescribirGuion() {
    if (!p.tiene_guion || ocupado || procesando || cambiandoPrioridad || inicioBloqueado || !salud.data?.ollama.listo) return;
    const ok = await confirmar({
      titulo: duracionGuardada == null ? '¿Reescribir el guion?' : `¿Reescribir el guion para unos ${numero(duracionGuardada, 2)} minutos?`,
      texto: <p>Se generará una versión nueva y se conservará el guion anterior. Los videos actuales quedarán desactualizados.</p>,
      aceptar: 'Reescribir guion',
    });
    if (ok) await lanzar({ tipo: 'guion' });
  }
  async function cambiarPrioridad(valor: string) {
    if (!prioridadDinamica) return;
    const baja = valor === 'baja';
    if (procesando || cambiandoPrioridad || guardandoVelocidades || (ocupado && !trabajo) || (ocupado ? prioridadActual : prioridadBaja) === baja) return;
    setCambiandoPrioridad(true);
    try {
      await Promise.all([
        cliente.cancelQueries({ queryKey: ['/trabajos'], exact: true }),
        cliente.cancelQueries({ queryKey: [baseProyecto(p.nombre)], exact: true }),
      ]);
      if (ocupado && trabajo) {
        const actualizado = await enviar<Trabajo>(`/trabajos/${encodeURIComponent(trabajo.id)}/prioridad`, { prioridad_baja: baja });
        cliente.setQueryData<Trabajo[]>(['/trabajos'], actuales => [...(actuales ?? []).filter(t => t.id !== actualizado.id), actualizado]);
        cliente.setQueryData<Detalle>([baseProyecto(p.nombre)], actual => actual ? {
          ...actual,
          trabajo: actualizado,
          preferencias: actualizado.prioridad_baja == null ? actual.preferencias : { ...actual.preferencias, prioridad_baja: actualizado.prioridad_baja },
        } : actual);
        if (actualizado.prioridad_baja !== baja) throw new Error('No se pudo confirmar el cambio de prioridad del trabajo. Revisa la prioridad que muestra el selector.');
        setPrioridadBaja(actualizado.prioridad_baja);
      } else {
        const preferencia = await enviar<{prioridad_baja: boolean}>(`${baseProyecto(p.nombre)}/prioridad`, { prioridad_baja: baja });
        cliente.setQueryData<Detalle>([baseProyecto(p.nombre)], actual => actual ? { ...actual, preferencias: { ...actual.preferencias, ...preferencia } } : actual);
        if (preferencia.prioridad_baja !== baja) throw new Error('No se pudo confirmar la preferencia de prioridad.');
        setPrioridadBaja(preferencia.prioridad_baja);
      }
      await cliente.invalidateQueries();
      avisar(`Prioridad ${baja ? 'baja' : 'alta'} ${ocupado ? 'aplicada' : 'guardada'}.`);
    } catch (e) { avisar((e as Error).message, true); } finally { setCambiandoPrioridad(false); }
  }
  async function actuar() {
    if (accion === 'ver' || accion === 'corregir') return ir(accion === 'ver' ? 'video' : 'guion');
    if (accion === 'cancelar') {
      const id = trabajo?.id;
      if (!id && !externo) return;
      const ok = await confirmar({ titulo: '¿Cancelar el trabajo?', texto: <p>{externo ? 'Este trabajo se lanzó desde otra terminal. Se detienen el proceso y todos sus procesos hijos.' : 'Se detienen el proceso y todos sus procesos hijos. Lo que ya quedó en caché se conserva.'}</p>, aceptar: 'Cancelar el trabajo', cancelar: 'Seguir', peligro: true });
      if (!ok || !id) return;
      setProcesando(true);
      try { await enviar(`/trabajos/${encodeURIComponent(id)}/cancelar`, { confirmar_externo: externo }); await cliente.invalidateQueries(); avisar('Trabajo cancelado.'); }
      catch (e) { avisar((e as Error).message, true); } finally { setProcesando(false); }
      return;
    }
    await lanzar({ tipo: accion === 'guion' ? 'guion' : ['retomar', 'reintentar'].includes(accion) ? 'continuar' : 'render', calidad });
  }

  const cifras = [progreso == null ? null : `${numero(progreso)} %${faseRender === 'animaciones' ? ' aprox. de animaciones' : ''}`, trabajo ? duracion(transcurrido) : null, restante ? `faltan unos ${tiempoLegible(restante)}` : null].filter(Boolean).join(' · ');
  return <div className="vc-resumen">
    <section className="vc-accion" aria-labelledby="accion-titulo">
      <h2 id="accion-titulo" className="vc-accion__titulo">{ocupado ? faseRender ? TITULOS_RENDER[faseRender] : `En curso: ${p.etapa}` : ETIQUETAS[accion]}</h2>
      <p className="m-0 text-texto-suave">{explicacion[accion]}</p>
      {faseRender && <>
        <ol className="vc-fases-render" aria-label="Fases del render">
          {FASES_RENDER.map((fase, i) => {
            const actual = i === indiceFase, hecha = i < indiceFase;
            const conFallos = hecha && fase.id === 'voces' && (vocesEstado?.fallidas ?? 0) > 0;
            return <li key={fase.id} aria-current={actual ? 'step' : undefined} data-hecha={hecha && !conFallos ? '' : undefined} data-fallos={conFallos ? '' : undefined}>
              <span className="vc-fases-render__numero" aria-hidden="true">{i + 1}</span>
              <span className="vc-fases-render__titulo">{fase.titulo}</span>
              <Insignia texto={conFallos ? 'con fallos' : hecha ? 'lista' : actual ? 'en curso' : 'pendiente'} color={conFallos ? 'rojo' : hecha ? 'verde' : actual ? 'amarillo' : 'gris'}/>
            </li>;
          })}
        </ol>
        {vocesEstado?.textos != null && <p className="vc-nota">{vocesEstado.omitidas ? `Sin narración: ${vocesEstado.omitidas} frases sin voz.` : `Preparación de voces: ${frasesSincronizadas}/${vocesEstado.textos} frases completas · ${vocesEstado.cacheados ?? 0} en caché · ${vocesEstado.pendientes ?? 0} pendientes · ${vocesEstado.fallidas ?? 0} fallos.`}</p>}
        {faseRender === 'voces' && <p className="vc-nota">{vocesEstado?.subfase === 'audio'
          ? `Generar audio: ${vocesEstado.audios_preparados ?? 0}/${vocesEstado.textos ?? 0} preparados; después se sincronizan las palabras.`
          : vocesEstado?.subfase === 'sincronizacion'
            ? `Sincronizando palabras: ${frasesSincronizadas}/${vocesEstado.textos ?? 0} frases listas. Después empiezan las animaciones.`
            : 'Primero se prepara la narración; después empiezan las animaciones de las escenas.'}</p>}
        {faseRender !== 'voces' && (vocesEstado?.fallidas ?? 0) > 0 && <p className="vc-nota">Manim reintenta durante la animación las frases que fallaron al preparar las voces.</p>}
      </>}
      <div className="vc-campo">
        <span className="vc-campo__etiqueta">Prioridad</span>
        <div><Selector etiqueta="Prioridad" valor={prioridadElegida} cambiar={valor => void cambiarPrioridad(valor)} deshabilitado={procesando || cambiandoPrioridad || guardandoVelocidades || (ocupado && !trabajo) || !prioridadDinamica} opciones={[{ valor: 'alta', texto: 'Alta' }, { valor: 'baja', texto: 'Baja' }]}/></div>
        <span className="vc-campo__ayuda" role="status">{!prioridadDinamica ? enDocker ? 'Docker usa los límites de CPU y memoria definidos en Compose. Este selector no cambia esos límites ni los procesos de Ollama o VoiceStudio del equipo anfitrión.' : 'El cambio de prioridad durante un trabajo solo está disponible en Windows. En este sistema no se ajustan los procesos de Ollama ni VoiceStudio.' : cambiandoPrioridad ? 'Cambiando la prioridad del trabajo…' : ocupado && !trabajo ? 'No se encontró el proceso para cambiar su prioridad.' : ocupado && prioridadActual == null ? 'La prioridad actual no está disponible. Elige Alta o Baja para cambiarla.' : AYUDA_PRIORIDAD}</span>
      </div>
      <RecursosTrabajo activo={ocupado && prioridadDinamica && ajustes.isSuccess}/>
      {ocupado ? <Progreso grande valor={progreso} mensaje={faseRender ? p.estado.mensaje : trabajo?.mensaje || p.mensaje || p.etapa} etiqueta={faseRender ? TITULOS_RENDER[faseRender] : undefined} cifras={cifras || undefined}/>
        : mostrarBarrido && <Progreso grande valor={100} estado="terminado" mensaje="Terminado"/>}
      {p.situacion === 'error' && <Mensaje tono="error">{p.mensaje}</Mensaje>}
      {bloqueado && <Mensaje tono="aviso" accion={<button className="vc-boton vc-boton--chico" onClick={() => void refrescarSalud(cliente).catch((e: Error) => avisar(e.message, true))}>Reintentar</button>}>{bloqueado}</Mensaje>}
      {ocupado && <div className="vc-fila-botones"><button className="vc-boton vc-boton--grande" disabled={procesando || cambiandoPrioridad || !trabajo} onClick={() => void actuar()}>{procesando ? 'Un momento…' : 'Cancelar'}</button></div>}
      {ocupado && externo && !trabajo && <p className="vc-nota">Para cancelarlo, detén el proceso desde la terminal que lo lanzó.</p>}
      {video && <Link className="vc-boton vc-boton--texto justify-self-start" to={`/proyectos/${encodeURIComponent(p.nombre)}?vista=video`}>Ver el video disponible{p.videos.every(v => v.desactualizado) ? ' (guion anterior)' : ''}</Link>}
      <section className="grid gap-4" aria-labelledby="opciones-render-proyecto-titulo">
        <h3 id="opciones-render-proyecto-titulo" className="m-0 text-base font-semibold">Opciones del video</h3>
        <OpcionesRender calidad={calidad} cambiar={setCalidad} deshabilitado={ocupado || procesando || guardandoDuracion || guardandoVelocidades || cambiandoPrioridad}/>
        <div className="vc-campo"><span className="vc-campo__etiqueta">Voz</span><div><Selector etiqueta="Voz" valor={voz} cambiar={setVoz} deshabilitado={ocupado || procesando} opciones={opcionesVoces}/></div><span className="vc-campo__ayuda">La voz se elige por separado de la resolución y los cuadros por segundo.</span></div>
      </section>
      <div className={`vc-campo${duracionValida ? '' : ' vc-campo--error'}`}>
        <label className="vc-campo__etiqueta" htmlFor="duracion-objetivo-proyecto">Duración del video final en minutos (opcional)</label>
        <div className="vc-fila-botones vc-duracion-objetivo">
          <input id="duracion-objetivo-proyecto" className="vc-campo__entrada" type="number" min={1} max={120} step="any" placeholder="Libre" value={duracionObjetivo} disabled={ocupado || procesando || guardandoDuracion || guardandoVelocidades} onChange={e => { setDuracionObjetivo(e.target.value); setEntradaDuracionInvalida(e.target.validity.badInput); }} aria-invalid={!duracionValida} aria-describedby="duracion-objetivo-proyecto-ayuda"/>
          <button className="vc-boton" disabled={ocupado || procesando || guardandoDuracion || guardandoVelocidades || !duracionValida || !duracionModificada} onClick={() => void guardarDuracion()}>{guardandoDuracion ? 'Guardando…' : 'Guardar duración'}</button>
        </div>
        <span id="duracion-objetivo-proyecto-ayuda" className={duracionValida ? 'vc-campo__ayuda' : 'vc-campo__error'}>{!duracionValida ? 'Escribe una duración de 1 a 120 minutos o deja el campo vacío.' : ocupado ? 'Puedes cambiar el objetivo cuando termine el trabajo actual.' : 'Se aplica al generar un guion nuevo. No reescala la voz ni modifica un guion existente. Vacío significa duración libre.'}</span>
        {duracionModificada && !ocupado && <span className="vc-campo__ayuda" role="status">Guarda la duración antes de iniciar otro trabajo.</span>}
      </div>
      {p.tiene_guion && !ocupado && <div className="vc-fila-botones">
        <button className="vc-boton" disabled={procesando || guardandoDuracion || inicioBloqueado || cambiandoPrioridad || !salud.data?.ollama.listo} onClick={() => void reescribirGuion()}>{duracionGuardada == null ? 'Reescribir guion' : 'Reescribir guion con esta duración'}</button>
      </div>}
      <section className="grid gap-4" aria-labelledby="velocidades-proyecto-titulo">
        <h3 id="velocidades-proyecto-titulo" className="m-0 text-base font-semibold">Velocidades del próximo render</h3>
        <div className="vc-dos-columnas">
          <div className={`vc-campo${velocidadVozValida ? '' : ' vc-campo--error'}`}>
            <label className="vc-campo__etiqueta" htmlFor="velocidad-voz-proyecto">Velocidad de la voz</label>
            <div className="vc-velocidad__control">
              <input id="velocidad-voz-proyecto" className="vc-campo__entrada" type="number" min={0.75} max={1.5} step={0.05} required value={velocidadVoz} disabled={ocupado || procesando || guardandoVelocidades || guardandoDuracion || cambiandoPrioridad} onChange={e => { setVelocidadVoz(e.target.value); setVozInvalida(e.target.validity.badInput || e.target.validity.stepMismatch); }} aria-invalid={!velocidadVozValida} aria-describedby="velocidad-voz-proyecto-ayuda"/>
              <output htmlFor="velocidad-voz-proyecto">{velocidadVozValida ? `${numero(factorVoz, 2)}×` : '—'}</output>
              <button type="button" className="vc-boton vc-boton--chico" disabled={ocupado || procesando || guardandoVelocidades || guardandoDuracion || cambiandoPrioridad} onClick={() => { setVelocidadVoz('1'); setVozInvalida(false); }} aria-label="Restablecer la velocidad de la voz a 1×">Restablecer 1×</button>
            </div>
            <span id="velocidad-voz-proyecto-ayuda" className="vc-campo__ayuda">De 0,75× a 1,5×. Cambia el ritmo y conserva el tono de la voz.</span>
          </div>
          <div className={`vc-campo${velocidadAnimacionesValida ? '' : ' vc-campo--error'}`}>
            <label className="vc-campo__etiqueta" htmlFor="velocidad-animaciones-proyecto">Velocidad de las animaciones</label>
            <div className="vc-velocidad__control">
              <input id="velocidad-animaciones-proyecto" className="vc-campo__entrada" type="number" min={0.5} max={2} step={0.05} required value={velocidadAnimaciones} disabled={ocupado || procesando || guardandoVelocidades || guardandoDuracion || cambiandoPrioridad} onChange={e => { setVelocidadAnimaciones(e.target.value); setAnimacionesInvalidas(e.target.validity.badInput || e.target.validity.stepMismatch); }} aria-invalid={!velocidadAnimacionesValida} aria-describedby="velocidad-animaciones-proyecto-ayuda"/>
              <output htmlFor="velocidad-animaciones-proyecto">{velocidadAnimacionesValida ? `${numero(factorAnimaciones, 2)}×` : '—'}</output>
              <button type="button" className="vc-boton vc-boton--chico" disabled={ocupado || procesando || guardandoVelocidades || guardandoDuracion || cambiandoPrioridad} onClick={() => { setVelocidadAnimaciones('1'); setAnimacionesInvalidas(false); }} aria-label="Restablecer la velocidad de las animaciones a 1×">Restablecer 1×</button>
            </div>
            <span id="velocidad-animaciones-proyecto-ayuda" className="vc-campo__ayuda">De 0,5× a 2×. Más rápidas mantienen las pausas de la narración; más lentas pueden alargar el video.</span>
          </div>
        </div>
        {!velocidadesValidas && <p className="vc-campo__error" role="alert">Revisa los límites de velocidad y usa pasos de 0,05×.</p>}
        <div className="vc-campo">
          <label className="vc-interruptor"><input type="checkbox" checked={vozFluida} disabled={ocupado || procesando || guardandoVelocidades || guardandoDuracion || cambiandoPrioridad} onChange={e => setVozFluida(e.target.checked)} aria-describedby="voz-fluida-proyecto-ayuda"/><span>Narración continua</span></label>
          <span id="voz-fluida-proyecto-ayuda" className="vc-campo__ayuda">Reduce pausas entre bloques sin regenerar tu voz.</span>
        </div>
        <p className="vc-campo__ayuda">1× es la velocidad original. Se aplican al próximo render sin reescribir el guion.{ocupado ? ' Podrás cambiarlas cuando termine el trabajo actual.' : ''}</p>
        <div className="vc-fila-botones"><button className="vc-boton" disabled={ocupado || procesando || guardandoVelocidades || guardandoDuracion || cambiandoPrioridad || !velocidadesValidas || !velocidadesModificadas} onClick={() => void guardarVelocidades()}>{guardandoVelocidades ? 'Guardando…' : 'Guardar velocidades'}</button></div>
        {velocidadesModificadas && !ocupado && <p className="vc-campo__ayuda" role="status">Guarda las velocidades antes de iniciar otro trabajo.</p>}
      </section>
      {!ocupado && <section className="vc-panel grid gap-4" aria-labelledby="resumen-render-proyecto-titulo">
        <h3 id="resumen-render-proyecto-titulo" className="m-0 text-base font-semibold">{p.tiene_guion ? 'Video que vas a renderizar' : 'Opciones seleccionadas'}</h3>
        <p className="m-0"><strong>{describirCalidad(calidad).nombre}</strong> · {nombreVoz}</p>
        <p className="vc-nota">{velocidadesValidas ? `Voz ${numero(factorVoz, 2)}× · Animaciones ${numero(factorAnimaciones, 2)}× · Narración continua ${vozFluida ? 'activada' : 'desactivada'}` : 'Revisa las velocidades antes de iniciar.'}</p>
        <p className="vc-nota">Duración objetivo: {duracionGuardada == null ? 'libre' : `${numero(duracionGuardada, 2)} min`} · Prioridad {prioridadBaja ? 'baja' : 'alta'}</p>
        <div className="vc-fila-botones"><button className="vc-boton vc-boton--principal vc-boton--grande" disabled={procesando || cambiandoPrioridad || Boolean(bloqueado) || (!['ver', 'corregir'].includes(accion) && inicioBloqueado)} onClick={() => void actuar()}>{procesando ? 'Un momento…' : ETIQUETAS[accion]}</button></div>
      </section>}
      {lineas.length > 0 && <details className="vc-plegable">
        <summary><ChevronRight aria-hidden="true"/>Últimas líneas del trabajo</summary>
        <Terminal titulo="Salida del trabajo">{lineas.slice(-200).join('\n')}</Terminal>
      </details>}
      <details className="vc-plegable">
        <summary><ChevronRight aria-hidden="true"/>Historial</summary>
        <ol className="vc-historial">{p.estado.historial?.slice().reverse().map((h, i) => <li key={i}><span>{h.etapa}</span><time>{fechaCorta(h.fecha)}</time></li>)}</ol>
      </details>
    </section>
    <aside className="grid gap-6 content-start">
      {video ? <figure className="m-0 grid gap-3">
        <img className="vc-marco" src={p.miniatura} alt={`Fotograma de ${p.titulo}`} data-flip-id={`miniatura-${p.nombre}`} ref={aplicarFlip}/>
        <figcaption className="vc-nota">{describirCalidad(video.calidad).nombre} · {duracion(video.duracion)} · {numero(video.megas)} MB{video.desactualizado ? ' · desactualizado' : ''}</figcaption>
      </figure> : <div className="vc-marco vc-marco--vacio">Sin video todavía</div>}
      <dl className="vc-datos">
        <dt>Fuente</dt><dd>{p.manifiesto.fuente.copia}</dd>
        {p.estado.guion?.escenas ? <><dt>Guion</dt><dd>{p.estado.guion.escenas} escenas · {numero(p.estado.guion.caracteres ?? 0, 0)} caracteres</dd></> : null}
        <dt>Duración objetivo</dt><dd>{duracionGuardada == null ? 'Libre' : `${numero(duracionGuardada, 2)} min`}</dd>
        <dt>Velocidad de voz</dt><dd>{numero(velocidadVozGuardada, 2)}×</dd>
        <dt>Velocidad de animaciones</dt><dd>{numero(velocidadAnimacionesGuardada, 2)}×</dd>
        <dt>Narración continua</dt><dd>{vozFluidaGuardada ? 'Activada' : 'Desactivada'}</dd>
        {duracionEstimada != null && duracionEstimada > 0 ? <><dt>Duración estimada del guion</dt><dd>unos {tiempoLegible(duracionEstimada)}</dd></> : null}
        {p.estado.guion?.modelo ? <><dt>Modelo</dt><dd>{p.estado.guion.modelo}</dd></> : null}
      </dl>
      <button className="vc-boton vc-boton--texto justify-self-start" onClick={() => ir('codigo')}>Ver el código de la fuente</button>
    </aside>
  </div>;
}
